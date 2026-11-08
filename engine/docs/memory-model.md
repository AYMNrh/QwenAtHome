# Memory model

Units are binary GiB/MiB unless explicitly stated. Estimates are single-sequence and model-specific. `bench/audit.py` emits per-layer encoded weight bytes, tensor types/shapes, metadata and a context/type matrix. Unsupported architectures, shard sets, tensor encodings or metadata/tensor contradictions fail closed.

## Formulae

For this GGUF, trunk layers = 65 - 1 MTP = 64; 16 dense attention and 48 recurrent layers. For KV type with block size B and encoded bytes E, a width-W row costs `(W/B)*E` bytes. K and V each have width 4*256 = 1024. f16 uses 2 bytes/element; q8_0 uses 34 bytes/32 elements; q4_0 uses 18 bytes/32 elements, including scales. Do not substitute nominal 4/8 bits.

`KV = padded_context * dense_layer_count * (K_row_bytes + V_row_bytes)`.

Context is rounded up to 256 cells for reference flash-attention budgeting. Enabled MTP adds its dense attention layer and its weights. Separate draft types and speculative rollback copies need separate budgets; first trials disable speculation.

`recurrent_bytes = 48 * state_rows * 4 * [(conv_kernel-1)*(inner + 2*groups*state) + state*inner]`.

One row: 149.625 MiB (5.625 MiB conv + 144 MiB delta state). Four rows: 598.5 MiB, matching historical MTP reference allocation. This is fixed-size live state per sequence/copy, not per-token KV. Host checkpoints, prefix snapshots and rollback add copies; they are not free. The runner disables context checkpoints and host prompt cache for its initial controlled tests.

Main-only encoded weights: about 10.953 GiB including shared tensors. MTP-specific layer weights are excluded when MTP is off. Tensor payload differs from mapped host file size and GPU residency. Actual backend residency/allocation is preserved in each raw log. Input embeddings/output tensors may remain CPU resident for partial GPU placement.

| Total context capacity | f16 KV GiB | q8_0 KV GiB | q4_0 KV GiB |
| --- | ---: | ---: | ---: |
| 8,192 | 0.5 | 0.266 | 0.141 |
| 32,768 | 2 | 1.0625 | 0.5625 |
| 86,016 (84 Ki tokens) | 5.25 | 2.789 | 1.477 |
| 131,072 | 8 | 4.25 | 2.25 |
| 262,144 | 16 | 8.5 | 4.5 |
| 524,288 (outside metadata limit) | 32 | 17 | 9 |

Total planning budget adds weights, live KV, recurrent rows, workspace, CUDA graph allocations, alignment/fragmentation and safety reserve. Default reserve is 1 GiB. Workspace/graph budgets remain null until measured; `unknown_overheads` never means verified fit. The estimator's hypothetical all-tensor GPU budget is conservative. The runner's all-layer GPU gate uses **trunk block weights only**, KV, recurrent state and reserve, excluding uncertain shared embedding/output residency; this avoids falsely claiming that a conservative weight estimate proves impossibility. Partial GPU placement is tested through the reference and is not incorrectly treated as a fully GPU-resident profile.

Main weights + 256K q4 KV alone exceed this GPU's capacity before sufficient workspace/reserve. 128K q4 may fit with some CPU weight placement, but quality must be compared against f16 at feasible lengths. 128K f16 KV plus main weights cannot all reside in 16GB. These are capacity calculations, not performance measurements.

## PCIe budget

An exact scheme that streams all dense-layer host KV for every token transfers at least the corresponding KV bytes per decode, before weight transfers, copies and synchronization. At a hypothetical 32 GB/s, 256K f16's 16 GiB alone costs about 0.537 s/token. This is a bandwidth-only illustrative bound, **not measured PCIe performance**. CPU attention can instead send queries/results but introduces its own host compute/bandwidth costs. Weight offload and KV offload are different experiments.

No host-tier attention implementation, eviction, sparse/window attention, lossy state compression or positional extension is implemented or silently enabled. 512K is refused by the runner until a deliberate extension experiment exists.
