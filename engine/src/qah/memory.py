"""Explicit single-sequence state budgets; estimates are not fit/quality claims."""
from .model import architecture

KV_TYPES = {'f16': (1, 2), 'f32': (1, 4), 'q8_0': (32, 34), 'q4_0': (32, 18)}


def estimate(model, context, key_type='f16', value_type='f16', mtp=False,
             recurrent_rows=1, workspace_bytes=None, graph_bytes=None,
             reserve_bytes=1024**3, gpu_budget_bytes=None):
    a = architecture(model)
    if context <= 0 or recurrent_rows < 1:
        raise ValueError('context and recurrent rows must be positive')
    # Reference pads KV cells for flash attention; row quantization includes block scales.
    cells = (context + 255) // 256 * 256
    def row(width, kind):
        block, encoded = KV_TYPES[kind]
        if width % block:
            raise ValueError('KV width incompatible with block quantization')
        return width // block * encoded
    per_layer = (row(a['kv_heads'] * a['key_dim'], key_type) +
                 row(a['kv_heads'] * a['value_dim'], value_type))
    kv = cells * per_layer * (len(a['full_attention_layers']) + (a['mtp_layers'] if mtp else 0))
    # f32 recurrent conv + delta state, per live row/checkpoint; not per token.
    recurrent = len(a['recurrent_layers']) * recurrent_rows * 4 * (
        (a['conv'] - 1) * (a['inner'] + 2 * a['groups'] * a['state']) + a['state'] * a['inner'])
    mtp_weights = sum(model['layer_weight_bytes'].get(str(i), 0)
                      for i in range(a['trunk_layers'], a['trunk_layers'] + a['mtp_layers']))
    weights = model['tensor_bytes'] - (0 if mtp else mtp_weights)
    trunk_weights = sum(model['layer_weight_bytes'].get(str(i), 0) for i in range(a['trunk_layers']))
    lower = weights + kv + recurrent + reserve_bytes
    complete = workspace_bytes is not None and graph_bytes is not None
    planned = lower + (workspace_bytes or 0) + (graph_bytes or 0)
    status = 'unknown_overheads' if not complete else 'estimated_fit'
    if gpu_budget_bytes is not None and planned > gpu_budget_bytes:
        status = 'refused_budget'
    if context > a['declared_context']:
        status = 'unsupported_positional_extension'
    return dict(context=context, padded_cells=cells, architecture=a, key_type=key_type,
                value_type=value_type, mtp=mtp, recurrent_rows=recurrent_rows,
                weight_bytes=weights, kv_bytes=kv, recurrent_bytes=recurrent,
                trunk_weight_bytes=trunk_weights,
                workspace_bytes=workspace_bytes, graph_bytes=graph_bytes,
                reserve_bytes=reserve_bytes, lower_bound_with_reserve_bytes=lower,
                planned_bytes=planned, gpu_budget_bytes=gpu_budget_bytes, status=status,
                placement='all tensors GPU (conservative; actual placement logged by backend)',
                tiered_kv_bytes_read_per_decode=kv,
                pcie_seconds_at_32GBps=kv / 32e9,
                pcie_bandwidth_is_measured=False)
