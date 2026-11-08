# QwenAtHome Engine

Run commands from this `engine/` directory. Set `MODEL_DIR` to your model directory and `LLAMA_SERVER` to your compatible llama-server executable; the comparison CLI reads these environment variables.

Published evidence is sanitized under `bench/evidence/`. Original full logs, local paths, generated-module working files and archived source snapshots remain local under `bench/results/` and are not published. Historical source/model hashes and null pre-commit SHAs are retained.

New specialized runtime, starting with independent GGUF inspection, memory planning and reproducible reference-backed execution. llama.cpp is an external reference and initial execution component. QAH does not yet contain an independent transformer graph or CUDA kernels. Existing ~84K context is the baseline to reproduce; 128K and 256K are investigation targets, 512K+ an experimental extension.

Requires Python 3.9+ (standard library only), a compatible llama-server binary, the GGUF, and NVIDIA driver tools for GPU telemetry. On this machine use `py -3.9`; the Python Store 3.10 launcher is inaccessible.

```powershell
py -3.9 -m unittest discover -s tests -v
py -3.9 bench/audit.py --model "$env:MODEL_DIR\Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf" --server "$env:LLAMA_SERVER" --checksum --output bench/results/audit-iq3.json
py -3.9 bench/run.py --model "$env:MODEL_DIR\Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf" --server "$env:LLAMA_SERVER" --contexts 8192 --trials 3 --tasks retrieval code decode --depths 0.1 0.5 0.9 --output bench/results/reference-f16.jsonl
py -3.9 bench/summary.py bench/results/reference-f16.jsonl --output bench/results/reference-f16-summary.json
```

For a controlled long-context probe, explicitly select lossy KV and CPU weight placement:

```powershell
py -3.9 bench/run.py --model "$env:MODEL_DIR\Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf" --server "$env:LLAMA_SERVER" --contexts 8192 32768 86016 131072 --trials 1 --generate 128 --key-type q4_0 --value-type q4_0 --gpu-layers 64 --tasks retrieval code decode --depths 0.5 --no-reuse --output bench/results/context-probes.jsonl
```

This one-trial command is a probe, not a statistically repeatable result. Use 3+ trials to estimate medians and nearest-rank p95 (small-sample p95 is only the maximum). Default runner matrix covers 8K, 32K, 84 Ki tokens (86,016), 128K, 256K and 512K; unsupported positional lengths and known all-GPU budget violations are recorded without allocating. These are total capacity sizes. Actual prompt length reserves generation plus one backend token; exact token-array length and SHA-256 are recorded.

Cold requests disable prompt reuse. Warm-prefix requests repeat the exact token array and compare deterministic outputs to cold; inspect `timings.cache_n` for actual reuse, not `tokens_cached` (which is state length after the request). Recurrent backends may fully reprocess even identical prompts. The tool-turn fixture is a controlled message-suffix/cache locality probe; it is not full OpenAI tool-call conformance or an actual coding-agent task.

`decode` forces the requested output length by explicitly ignoring EOS and measures sustained decode near filled context. That choice is logged and **only applies to the throughput probe**. Quality fixtures honor EOS and use strict exact-match answers. Repeated, varied filler is disclosed in results; retrieval, a small three-file dependency tracing task and forced decoding do not establish real coding-agent tasks/minute.

Each server is isolated on loopback, uses one slot, disables automatic fit, context shifting, speculation and host prompt-cache/checkpoints, and is terminated after its trial. Timeouts/failures are outcomes. `--allocation-only` loads and warms up the model, records allocation details and makes no prefill/decode/quality claim. Check `reference_argv`, actual generation settings and verbosity-4 allocation logs for precise residency and behavior. No existing server is modified. Results are local ignored artifacts under `bench/results/`; summary never turns failed/unknown quality into success.

Completed-request rows include model and binary checksums, reference build/commit, source hash, repository commit (null while unborn), dirty status, exact prompt size/hash, generation, seed/sampling, KV types, placement flags, phase timings, sampled memory peaks and raw-log path. Allocation/gate rows explicitly omit unmeasured request phases. See `bench/schema.json`, `docs/architecture-audit.md`, `docs/memory-model.md`, `docs/benchmark-results.md`, and `docs/progress.md`. No commits or pushes have been made.

## Preferred-model comparison

Huihui abliterated is the user-preferred candidate. `bench/compare.py` checks both model checksums against the retained QwenAtHome baseline and compares matched settings. It reuses that repository's three executable coding checks with the native chat template. Generated Python is AST-screened and run in separate `python -I` processes with an eight-second timeout; the filter is not a security sandbox.

```powershell
py -3.9 bench/compare.py --contexts 32768 --depths 0 3 --trials 3 --tasks coding --output bench/results/compare-coding-32k.jsonl
py -3.9 bench/compare.py --contexts 32768 84992 --depths 3 --trials 1 --tasks retrieval decode --output bench/results/compare-context.jsonl
py -3.9 bench/summary.py bench/results/compare-coding-32k.jsonl --output bench/results/compare-coding-32k-summary.json
```

These comparison runs enable fit on/512 MiB target, GPU sampling, Jinja, prefix checkpoints and MTP as selected. Target batch/microbatch is 512/128; main KV is q4_0 and draft KV q8_0. `--draft-ubatch` controls only the draft's physical microbatch. Cold coding explicitly disables prefix reuse. Warm retrieval reports actual cached input tokens. Non-streaming coding TTFT is null; HTTP elapsed time is measured. The summary separates MTP depth and speculation settings.

A failed reference fit-margin check is refused before prefill. `--allow-memory-pressure` explicitly overrides that safeguard for a deliberate pressure experiment; it does not change attention or positional semantics. The original `bench/run.py` remains the MTP-off baseline runner. Results and limits are in `docs/model-comparison.md`.
