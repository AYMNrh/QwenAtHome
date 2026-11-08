"""Read GGUF v2/v3 directories without loading weights or importing llama.cpp."""
import hashlib
import math
import re
import struct
from pathlib import Path


# GGML block size, encoded bytes; unsupported formats fail rather than guess.
TYPES = {0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20),
         6: (32, 22), 7: (32, 24), 8: (32, 34), 9: (32, 40),
         10: (256, 84), 11: (256, 110), 12: (256, 144),
         13: (256, 176), 14: (256, 210), 15: (256, 292),
         16: (256, 66), 17: (256, 74), 18: (256, 98),
         19: (256, 50), 20: (32, 18), 21: (256, 110),
         22: (256, 82), 23: (256, 136), 24: (1, 1),
         25: (1, 2), 26: (1, 4), 27: (1, 8), 28: (1, 8),
         29: (256, 56), 30: (1, 2)}
SCALARS = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i',
           6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect_gguf(path, checksum=False):
    path = Path(path).resolve()
    size = path.stat().st_size
    with path.open('rb') as stream:
        def read(n):
            if n < 0 or n > size - stream.tell():
                raise ValueError('truncated or invalid GGUF length')
            value = stream.read(n)
            if len(value) != n:
                raise ValueError('truncated GGUF')
            return value

        def unpack(fmt):
            return struct.unpack('<' + fmt, read(struct.calcsize('<' + fmt)))[0]

        def string(keep=True):
            n = unpack('Q')
            if keep:
                return read(n).decode('utf-8')
            if n > size - stream.tell():
                raise ValueError('invalid string length')
            stream.seek(n, 1)

        def value(kind, keep=True, depth=0):
            if depth > 4:
                raise ValueError('excessive GGUF array nesting')
            if kind in SCALARS:
                return unpack(SCALARS[kind])
            if kind == 8:
                return string(keep)
            if kind == 9:
                item_kind, count = unpack('I'), unpack('Q')
                if count > size:
                    raise ValueError('invalid GGUF array count')
                if keep:
                    return [value(item_kind, True, depth + 1) for _ in range(count)]
                for _ in range(count):
                    value(item_kind, False, depth + 1)
                return {'count': count, 'element_type': item_kind, 'omitted': True}
            raise ValueError('unknown GGUF metadata type %s' % kind)

        if read(4) != b'GGUF' or unpack('I') not in (2, 3):
            raise ValueError('expected little-endian GGUF v2/v3')
        tensor_count, metadata_count = unpack('Q'), unpack('Q')
        if tensor_count > size // 24 or metadata_count > size // 12:
            raise ValueError('invalid GGUF directory counts')
        metadata = {}
        for _ in range(metadata_count):
            key, kind = string(), unpack('I')
            if key in metadata:
                raise ValueError('duplicate metadata key ' + key)
            metadata[key] = value(kind, not key.startswith(('tokenizer.ggml.tokens',
                                                         'tokenizer.ggml.merges',
                                                         'tokenizer.ggml.token_type')))
        if metadata.get('split.count', 1) != 1:
            raise ValueError('split GGUF requires a complete shard loader (not yet implemented)')
        tensors, names = [], set()
        for _ in range(tensor_count):
            name, ndim = string(), unpack('I')
            if name in names or not 1 <= ndim <= 4:
                raise ValueError('duplicate tensor or invalid rank: ' + name)
            names.add(name)
            dims = [unpack('Q') for _ in range(ndim)]
            kind, offset = unpack('I'), unpack('Q')
            if kind not in TYPES:
                raise ValueError('unsupported GGML tensor type %s' % kind)
            block, encoded = TYPES[kind]
            if not all(dims) or dims[0] % block:
                raise ValueError('invalid quantized tensor shape: ' + name)
            tensors.append(dict(name=name, shape=dims, type=kind, offset=offset,
                                bytes=math.prod(dims) // block * encoded))
        alignment = metadata.get('general.alignment', 32)
        if alignment <= 0 or alignment & (alignment - 1):
            raise ValueError('invalid alignment')
        data_start = (stream.tell() + alignment - 1) // alignment * alignment
        previous_end = 0
        for tensor in sorted(tensors, key=lambda t: t['offset']):
            offset = tensor['offset']
            if offset % alignment or offset < previous_end or data_start + offset + tensor['bytes'] > size:
                raise ValueError('overlapping, unaligned or truncated tensor: ' + tensor['name'])
            previous_end = offset + tensor['bytes']
    layers = {}
    for tensor in tensors:
        match = re.match(r'blk\.(\d+)\.', tensor['name'])
        group = match[1] if match else 'shared'
        layers[group] = layers.get(group, 0) + tensor['bytes']
    return dict(path=str(path), file_bytes=size, sha256=sha256(path) if checksum else None,
                metadata=metadata, tensors=tensors, layer_weight_bytes=layers,
                tensor_bytes=sum(t['bytes'] for t in tensors), data_offset=data_start)


def architecture(model):
    m = model['metadata']
    arch = m['general.architecture']
    if arch != 'qwen35':
        raise ValueError('memory layout not validated for architecture ' + arch)
    def get(key):
        return m[arch + '.' + key]
    total, mtp = get('block_count'), m.get(arch + '.nextn_predict_layers', 0)
    trunk = total - mtp
    explicit = m.get(arch + '.attention.recurrent_layers')
    interval = m.get(arch + '.full_attention_interval', 4)
    if interval <= 0 or not 0 < trunk <= total:
        raise ValueError('invalid qwen35 layer layout')
    if explicit is not None and (not isinstance(explicit, list) or len(explicit) != total):
        raise ValueError('invalid recurrent layer map')
    recurrent = [i for i in range(trunk) if (explicit[i] if explicit is not None else (i + 1) % interval != 0)]
    full = [i for i in range(trunk) if i not in recurrent]
    # Confirm metadata layout against actual recurrent/full-attention tensor families.
    names = {t['name'] for t in model['tensors']}
    for i in range(trunk):
        marker = 'ssm_conv1d.weight' if i in recurrent else 'attn_k.weight'
        if 'blk.%d.%s' % (i, marker) not in names:
            raise ValueError('layer %d tensor layout contradicts metadata' % i)
    return dict(name=arch, trunk_layers=trunk, mtp_layers=mtp,
                recurrent_layers=recurrent, full_attention_layers=full,
                declared_context=get('context_length'), kv_heads=get('attention.head_count_kv'),
                key_dim=get('attention.key_length'), value_dim=get('attention.value_length'),
                conv=get('ssm.conv_kernel'), inner=get('ssm.inner_size'),
                state=get('ssm.state_size'), groups=get('ssm.group_count'))
