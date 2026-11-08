# Architecture audit — 2026-11-08

## Verified locally

The repository initially contained only `.git`, with an unborn `master` and no submodules or implementation. `<LOCAL_PATH>/llama.cpp` is a binary distribution, not a source checkout. The selected reference binary is `<LOCAL_PATH>/llama-server.exe`: build 12110, commit `cd959bae9`, Clang 20.1.8. It supports CUDA sm_120 according to its startup log. No upstream binary or model was modified.

Selected starting artifact (smallest available 27B variant, not necessarily the user's historical baseline):

- `<LOCAL_PATH>/Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf`
- SHA-256 `eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19`
- File: 12,120,016,416 bytes; tensor payload: 12,109,021,184 bytes; 866 validated tensors.
- `general.architecture=qwen35`; 65 stored blocks, one next-token prediction block; 64 trunk blocks.
- Dense attention at trunk indices 3, 7, ..., 63: 16 layers. Recurrent gated-delta network at the other 48 indices, independently checked against tensor names.
- Embedding 5120; FFN 17408; query heads 24; KV heads 4; K/V head dimensions 256; GQA ratio 6. Head dimensions must not be derived by dividing embedding width by query heads.
- Recurrent convolution width 4, state size 128, inner width 6144, groups 16, time-step rank 48.
- RoPE base 10,000,000; dimension count 64; sections [11,11,10,0]. Declared context 262,144.
- GPT2-style tokenizer, `qwen35` pretokenizer; 248,320 vocabulary entries; 247,587 merges. EOS 248046, BOS/padding 248044; add_bos=false. Chat template preserved in audit JSON. Bench uses an explicitly logged text-only Qwen message envelope and closed-think prefill, not the full Jinja tool template.
- Mixed quantization: inspect the per-tensor type/size list, not just the filename or general file type. IQ3 file includes IQ1_M tensors. MTP weights are present but speculation is disabled for the first reference tests.

Also available: `Qwen3.8-27B-UD-IQ4_XS.gguf` (14,252,845,984 bytes) and `Qwen3.8-27B-UD-Q3_K_XL.gguf` (13,146,393,504 bytes). These have not yet been independently audited/checksummed. An old log for IQ4_XS at 32K shows q4 KV and MTP, not enough provenance to establish the user's ~84K/~70 tok/s baseline.

## Hardware and unknowns

Live `nvidia-smi`: RTX 5070 Ti, 16,303 MiB, WDDM, driver 621.14. Driver reports CUDA UMD 13.5; installed `nvcc` is 12.6.85. Existing CUDA13 reference binary executes without rebuilding. Idle PCIe query reports generation 1, width x16; this is a power-state observation, not a load-bandwidth measurement.

CPU is user supplied and corroborated by historical llama.cpp logs (7800X3D). Current CIM access was denied. Live Windows GlobalMemoryStatusEx confirms physical RAM 67,684,352,000 bytes (about 64,548.8 MiB). PCIe during inference reports Gen5 x16. Benchmark telemetry samples live reference-process peak working set via Windows APIs, and device-wide VRAM via nvidia-smi. Device-wide counters include desktop apps; sampling can miss transient peaks. Host commit availability is captured at run start; pinned memory, NVMe and PCIe transfer bandwidth remain unknown.

## Pinned reference sources

Architecture and state formula checked against upstream at the binary's commit:

- [qwen35.cpp](https://github.com/ggml-org/llama.cpp/blob/cd959bae9/src/models/qwen35.cpp)
- [llama-hparams.cpp](https://github.com/ggml-org/llama.cpp/blob/cd959bae9/src/llama-hparams.cpp)
- [llama-memory-recurrent.cpp](https://github.com/ggml-org/llama.cpp/blob/cd959bae9/src/llama-memory-recurrent.cpp)
- [llama-model.cpp placement](https://github.com/ggml-org/llama.cpp/blob/cd959bae9/src/llama-model.cpp#L1666): placement start is `max(n_layer_all + 1 - n_gpu_layers, 0)`. The input embedding is CPU resident. Thus requesting 64 GPU layers on a 65-block artifact leaves trunk layers 0 and 1 on CPU, despite MTP being disabled. Logs confirm 6.23 MiB recurrent state on CPU. With 48 requested slots, trunk layers 0 through 17 are CPU placed, including four dense-attention layers and fourteen recurrent layers. The benchmark records allocation breakdowns rather than equating the layer flag with residency.

These establish semantics for this reference version. No model-card quality claim has been inferred from filenames or metadata.
