# Running the recorded profiles

## Requirements

The recorded dense-model runtime was official llama.cpp b12110 (`cd959bae9`), Windows CUDA 13.4. Download the corresponding runtime and selected GGUF yourself; neither binaries nor weights are in this repository. Later builds may change CLI names, output, and performance. Verify downloaded checksums against the model publisher.

Set `LLAMA_SERVER` to the executable's full path and `MODEL_DIR` to the directory holding the GGUF files. For example, in PowerShell, using your actual locations:

```powershell
$env:LLAMA_SERVER = Join-Path $PWD 'runtime/llama-server.exe'
$env:MODEL_DIR = Join-Path $PWD 'models'
& ./profiles/Start-Huihui-Qwen38.cmd
```

Keep the server terminal open. Open http://127.0.0.1:8081 after it loads. Stop the existing server before launching another; every profile uses the same port. The scripts check required environment variables but do not download models, kill processes, alter clocks, or change the page file.

## Profiles

| Launcher | Target | Context | Main KV | Speculation |
|---|---|---:|---|---|
| Start-Qwen38-General.cmd | Unsloth UD-IQ4_XS | 32,768 | Q4_0 | MTP 3 |
| Start-Qwen38.cmd | Unsloth UD-IQ4_XS | 32,768 | Q4_0 | MTP 3 + ngram-simple key 8 / draft 64 |
| Start-Qwen38-Q3-85K.cmd | Unsloth UD-Q3_K_XL | 84,992 | Q4_0 | MTP 3 |
| Start-Huihui-Qwen38.cmd | Huihui GSQ-RCO IQ3_S-mtp | 32,768 | Q8_0 | MTP 3 |

Shared: full GPU layers, Flash Attention, GPU sampling, one slot, batch 512, microbatch 128, eight CPU threads, Q8_0 draft KV. Interactive defaults: temperature 1, top-p .95, top-k 20, min-p 0, repetition penalty 1, default template reasoning behavior. Benchmark requests can override those defaults.

The recorded 85K profile has very little VRAM headroom. A successful retrieval run is not proof it is robust under other applications or all agent workloads. No automatic stop/start or system-memory changes are hidden in these scripts.

## API and Hermes

Use an OpenAI-compatible Chat Completions endpoint at `http://127.0.0.1:8081/v1`. The Huihui model alias is `Huihui-Qwen3.8-27B`; other launchers use `Qwen3.8-27B`. The historical local server did not require a key and bound only to localhost. Do not publish actual credentials in documentation. Match a client/Hermes context override to the serving profile, rather than the larger native context advertised by model metadata. Refresh the UI and choose the matching alias after switching models.

Hermes supports automatic compaction, but it was researched rather than verified through a complete local agent workflow. See [official context documentation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md).

## Strata Flash baseline settings

Recorded terminal 0.2.7 / engine 0.1.52; Flash Next IQ2_XS; 32K; vision off; MTP on; KV int8; `--expert-cache auto --prefill auto --spec 4 --spec-min-p 0.5 --vram-reserve-mib 1500`. Default route-tail-skip 7 remained enabled, so this was not a claim of bit-identical full-model arithmetic.

Strata setup had prepared native model/pack/MTP directories. Their machine-specific paths and configuration files are not published. An install was staged using `strata install -- ... --no-start`; launch then used a saved Flash preset. Use the matching version's help for data-directory and preset handling. The IQ2_XS shards together occupy about 68 GB decimal on disk, distinct from runtime resident memory.

At 64K, a Windows commit warning prevented further testing. Available physical RAM alone does not establish commit headroom; no page-file modification was performed. `--kv-grow` is a separate Strata memory mode; it was not applied in these local Flash measurements.
