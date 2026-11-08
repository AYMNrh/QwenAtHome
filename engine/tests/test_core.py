import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'bench'))
from qah.model import inspect_gguf
from qah.memory import estimate
from summary import summarize
from run import allocations


def tiny_model():
    m = {'general.architecture': 'qwen35'}
    m.update({'qwen35.' + k: v for k, v in dict(
        block_count=5, nextn_predict_layers=1, context_length=262144,
        full_attention_interval=4).items()})
    m.update({'qwen35.' + k: v for k, v in {
        'attention.head_count_kv': 4, 'attention.key_length': 256, 'attention.value_length': 256,
        'ssm.conv_kernel': 4, 'ssm.inner_size': 6144, 'ssm.state_size': 128, 'ssm.group_count': 16}.items()})
    tensors = [dict(name='blk.%d.%s' % (i, 'attn_k.weight' if i == 3 else 'ssm_conv1d.weight')) for i in range(4)]
    return dict(metadata=m, tensors=tensors, tensor_bytes=10000, layer_weight_bytes={'4': 1000})


class CoreTests(unittest.TestCase):
    def test_mtp_allocation_parser_keeps_main_and_draft_caches(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'server.log'
            log.write_text('CUDA0 KV buffer size = 576.00 MiB\n'
                           'CUDA0 KV buffer size = 68.00 MiB\n'
                           'CUDA0 compute buffer size = 161.00 MiB\n'
                           'CUDA0 compute buffer size = 161.00 MiB\n')
            result = allocations(log)
            self.assertEqual(result['CUDA0_KV_bytes'], 644 * 1024**2)
            self.assertEqual(result['CUDA0_compute_bytes'], 161 * 1024**2)

    def test_gguf_directory_and_truncation(self):
        def string(text):
            data = text.encode()
            return struct.pack('<Q', len(data)) + data
        header = b'GGUF' + struct.pack('<IQQ', 3, 1, 1)
        header += string('general.architecture') + struct.pack('<I', 8) + string('test')
        header += string('weight') + struct.pack('<IQIQ', 1, 32, 8, 0)
        data = header + b'\0' * (-len(header) % 32) + b'\0' * 34
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tiny.gguf'
            path.write_bytes(data)
            model = inspect_gguf(path, checksum=True)
            self.assertEqual(model['tensor_bytes'], 34)
            self.assertEqual(len(model['sha256']), 64)
            path.write_bytes(data[:-1])
            with self.assertRaisesRegex(ValueError, 'truncated tensor'):
                inspect_gguf(path)

    def test_hybrid_memory_accounting_and_gates(self):
        model = tiny_model()
        result = estimate(model, 131072, 'q4_0', 'q4_0', recurrent_rows=4,
                          gpu_budget_bytes=1)
        self.assertEqual(result['kv_bytes'], 131072 * 2 * 1024 // 32 * 18)
        self.assertEqual(result['recurrent_bytes'], 3 * 4 * 4 * (3 * (6144 + 2 * 16 * 128) + 128 * 6144))
        self.assertEqual(result['weight_bytes'], 9000)
        self.assertEqual(result['status'], 'refused_budget')
        self.assertEqual(estimate(model, 524288)['status'], 'unsupported_positional_extension')
        self.assertEqual(estimate(model, 131072, mtp=True)['kv_bytes'], 2 * 131072 * 2 * 1024 * 2)
        bad = copy.deepcopy(model)
        bad['tensors'][0]['name'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            estimate(bad, 8192)

    def test_summary_never_counts_failed_or_unknown_quality_as_pass(self):
        row = dict(model_sha256='m', provenance=dict(source_sha256='s'), context=131072,
                   status='ok', measurement=dict(ttft_seconds=2, elapsed_seconds=4),
                   quality_pass=None)
        failed = dict(row, status='failed', quality_pass=True)
        result = summarize([row, failed])[0]
        self.assertEqual((result['successes'], result['trials']), (1, 2))
        self.assertEqual(result['quality_measured'], 0)
        self.assertEqual(result['quality_passes'], 0)
        self.assertEqual(result['ttft_seconds'], dict(n=1, median=2, p95=2))
        # Speculation is a separate experiment, never pooled into a speed median.
        mtp = dict(row, mtp_depth=3, speculation='draft-mtp')
        self.assertEqual(len(summarize([row, mtp])), 2)


if __name__ == '__main__':
    unittest.main()
