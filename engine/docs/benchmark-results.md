# Measured reference results - 2026-11-08

Publication note: evidence links below contain sanitized records. Full logs and archived source snapshots remain local; their paths are placeholders. Historical source hashes identify the original runs, not these redacted records.

These establish an executable foundation and expose quality failures. They do not establish an independent transformer runtime, an optimization, or validated useful 128K/256K context.

## Provenance

- Model: `<LOCAL_PATH>/Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf`.
- Model SHA-256: `eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19`.
- Reference: `version: 0.9.0-dev (build 12110, commit cd959bae9); built with Clang 20.1.8 for Windows x86_64`.
- Reference executable SHA-256: `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`.
- Repository HEAD: unborn; commit SHA is null. Each row includes source SHA-256, dirty status, exact argv and settings. Final baseline/allocation runs archive source snapshots. No commits were made.
- RTX 5070 Ti 16,303 MiB, driver 621.14, Ryzen 7800X3D; live physical RAM 67,684,352,000 bytes. OS/Python/current memory inventory are in final rows.
- Exact token-array prompts; temperature 0, top_k=1, top_p=1, min_p=0, repeat penalty 1; MTP/speculation off, flash attention on, no context shifting/fit/host prefix cache/checkpoints. Seeds 1729 through 1731 for baseline; 1729 for one-trial probes.
- Closed-think text-only message envelope, repeated inventory filler, strict exact-match scoring. Forced decode ignores EOS explicitly and requests 128 tokens. Backend decode rates exclude first-token time; generation counts/settings/timings are preserved.

## Repeated f16 attention-state reference (8,192 total capacity)

All trunk attention/recurrent computation is on GPU; input embedding remains CPU mapped. Every prompt has 8,063 tokens. Three cold trials per task; p95 is nearest-rank and equals the maximum at n=3.

| Task | Quality | Complete 128-token decodes | Median TTFT s | p95 TTFT s | Median backend decode tok/s | p95 tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| retrieval | 3/3 | 0/3 | 4.128 | 4.132 | 50.377 | 50.557 |
| code | 0/3 | 0/3 | 4.035 | 4.105 | 51.936 | 52.063 |
| decode | not scored | 3/3 | 4.040 | 4.047 | 52.348 | 52.665 |

## Context truth table: q4_0 K and V (lossy)

One trial per context/task, midpoint needle only. Requested 64 GPU placement slots: 62 active trunk layers plus output on GPU, two recurrent trunk layers on CPU. Dense attention still retains full history. These differ from the f16 reference in both KV type and placement, so rate differences do not isolate a cause.

| Total capacity | Exact prompt tokens | Prefill completed | Needle exact match | Code task | Forced 128-token decode | Decode TTFT s | Backend decode tok/s | Sampled trial VRAM peak MiB |
| ---: | ---: | --- | --- | --- | --- | ---: | ---: | ---: |
| 8192 | 8063 | yes | pass (1/1) | FAIL | complete | 4.290 | 35.493 | 13229 |
| 32768 | 32639 | yes | pass (1/1) | FAIL | complete | 20.843 | 31.385 | 13769 |
| 86016 | 85887 | yes | pass (1/1) | FAIL | complete | 81.154 | 26.828 | 15055 |
| 131072 | 130943 | yes | pass (1/1) | FAIL | complete | 164.922 | 22.679 | 15792 |

Device VRAM counters include other applications, are sampled, and can miss peaks; the per-row memory scope is cumulative within the trial. WDDM paging/residency pressure is not independently measured. The 128K probe had far less than 1 GiB free and is not a safe production profile. All code-task failures are retained: the model returned Python instead of the requested integer 61. This also fails at 8K f16, so it is not evidence of a long-context-only regression.

## Larger-context allocation and planner outcomes

- 128K f16 and 256K f16: all-trunk GPU budget gate refuses (weights + native state + 1 GiB reserve exceed free VRAM). This does not rule out slower CPU placement.
- 128K q4_0: all-trunk GPU load/warmup succeeded in the final allocation-only run; full prefill/decode/needle measurements above use the separately identified 64-slot placement.
- 256K q4_0: all-trunk GPU budget gate refuses. With 48 requested slots, load/warmup succeeds: four dense-attention layers and fourteen recurrent layers are CPU placed. No full 256K prefill, sustained decode or recall test was run. Allocation is not useful-context validation.
- 512K: refused before loading because 524,288 exceeds the declared 262,144 positional context. No RoPE override or approximate attention is silently applied.

Allocation buffer counts are rounded backend log values, not exact allocator/driver peaks. The partial 256K placement logs 1,152 MiB CPU KV and 3,456 MiB GPU KV, summing to the estimator's 4,608 MiB. Recurrent-state allocation totals about 149.62 MiB; live compute buffers are separately logged. Graph memory/fragmentation, state checkpoints, actual PCIe bandwidth and transfer counters remain unresolved.

## Limits and next gates

- Initial smoke showed identical cold/warm deterministic output, but cache_n=0: no measured prefix-reuse benefit. The initial malformed tool-prefix fixture failed; it is diagnostic and was corrected. Corrected protocol/locality behavior still needs a dedicated validation run.
- The original smoke decode hit the capacity boundary; it is excluded from sustained-throughput evidence. Subsequent probes reserve one additional token and require no truncation.
- No per-layer/logit parity against an independent graph exists yet; no MTP acceptance, rollback correctness, end-to-end coding-agent tasks/minute, 30-minute stability or custom-kernel gain is established.
- Phase 0 gate passed. Phase 1 has a runnable harness and measured truth table, but useful-context quality/repeatability and tool reuse gates remain open. The next work is representative task/scoring validation, repeated multi-depth 128K experiments, then full 256K CPU-placement prefill/decode/quality with measured transfer cost. Later runtime optimization remains gated.

## Local evidence and reruns

- [Baseline sanitized JSONL](../bench/evidence/baseline-f16.jsonl), [baseline summary](../bench/evidence/baseline-f16-summary.json).
- [Context probes JSONL](../bench/evidence/context-probes.jsonl), [context summary](../bench/evidence/context-probes-summary.json).
- [Verified all-GPU allocation checks](../bench/evidence/allocation-verified-q4.jsonl), [256K partial-placement allocation](../bench/evidence/allocation-256k-cpu.jsonl).
- Source hash, binary hash, fixture hash, source snapshot (where captured), exact prompts/generation/sampling, allocation breakdowns, raw logs and errors are in each result. Early probes have source hashes but predate snapshot capture; do not treat them as an archived release.
- `allocation-q4.jsonl` gate rows for 64 requested layers and the interrupted `quantized-matrix.jsonl` are diagnostic, superseded evidence. The final gate correctly accounts for 65 stored blocks plus the output placement slot.
- See README for executable commands; results remain local ignored artifacts. No production profiles were published.
