# Q3_K_XL vs preferred Huihui abliterated — 2026-11-08

Publication note: evidence links below contain sanitized records. Full logs and archived source snapshots remain local; their paths are placeholders. Historical source hashes identify the original runs, not these redacted records.

Keep Huihui as the preferred model for further engine work. It passed all three focused coding checks with MTP3; Q3_K_XL failed fresh code. This is a small fixed-fixture comparison, not a broad model ranking or an independent engine speedup. No persistent server or deployment was changed.

## Matched short coding measurements

32,768 allocated context; actual short prompt counts and generated counts are recorded per row. Both models use q4_0 main K/V, q8_0 draft K/V, full GPU trunk placement, flash attention, GPU sampling, batch 512/microbatch 128, the native Jinja chat API, thinking off, seed 42, temperature 0 and a 1,600-token output cap. MTP is disabled or depth 3. Prompt cache is disabled for cold coding requests (reported cache_n=0).

Three repeats of each of the same three published executable checks. Repeated output hashes within each profile/task were identical. Repeats measure timing variability, not nine independent tasks. Validation uses the retained upstream checks; Markdown fences can pass after code extraction, so this is functional correctness rather than strict output-format conformance.

| Task | Huihui MTP0: median tok/s; pass | Huihui MTP3 | Q3 MTP0 | Q3 MTP3 |
| --- | --- | --- | --- | --- |
| bugfix | 50.72; 3/3 | 125.94; 3/3 | 47.35; 3/3 | 123.86; 3/3 |
| multi_function_edit | 50.49; 3/3 | 115.26; 3/3 | 47.97; 3/3 | 116.66; 3/3 |
| fresh_code | 52.21; 0/3 | 96.92; 3/3 | 48.28; 0/3 | 98.27; 0/3 |

| MTP3 task | Huihui median HTTP seconds | Q3 median HTTP seconds |
| --- | ---: | ---: |
| bugfix | 2.076 | 2.061 |
| multi_function_edit | 1.748 | 1.684 |
| fresh_code | 6.772 | 9.830 |

Failed outputs still have measured generation speeds; they do not count as completed tasks. HTTP times include prefill and generation but exclude validation/startup, and are not a full agent tasks/minute measure. Native chat TTFT is null because this comparison used non-streaming chat.

## MTP and correctness limits

Huihui edit outputs are byte-identical with MTP off/on; its fresh-code output differs and only MTP3 passes. Q3 fresh code fails by calling next() on a list. Huihui MTP-off fresh code violates the lazy-consumption check. We do not claim general deterministic/logit equivalence across MTP settings. Layer/logit parity and near-tie numerical behavior remain unresolved. MTP draft counts/acceptance, outputs and validation errors are retained in sanitized JSONL.

## Filled-context probes

MTP3, same main/draft KV precision and placement. Context is total capacity. Midpoint needle probes honor EOS; the separate parser-generation probe explicitly ignores EOS for 128 tokens and is not quality-scored. Prompts use the model-rendered chat template, exact token-array length, fixed seed and disclosed repeated archive filler. One cold/warm/decode probe per context/model; no long-context medians are claimed.

| Model | Capacity | Exact prompt tokens | Cold retrieval seconds | Warm seconds | Needle cold/warm | 128-token parser decode tok/s | Sampled device-wide VRAM peak MiB |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| huihui | 32768 | 32511 | 26.097 | 0.286 | pass/pass | 73.59 | 15036 |
| q3 | 32768 | 32511 | 25.370 | 0.274 | pass/pass | 75.39 | 15328 |
| huihui | 84992 | 84735 | 106.669 | 0.441 | pass/pass | 56.21 | 15884 |

Q3 at 84,992 did not complete the original matched prefill. Its latest logged progress was 47,616 tokens at 300.36 seconds of server-reported prefill time; the last 512 tokens took about 57 seconds. Free VRAM was observed around 126–249 MiB. The operator stopped the severe slowdown and retained a cancelled outcome, not an OOM, timeout or completed benchmark. The reference log explicitly says it cannot meet the requested 512 MiB margin. Exact WDDM paging cause is unprofiled.

## Targeted workspace experiment

Tested draft microbatch 4 versus inherited 128, leaving the target microbatch 128 and MTP depth 3 unchanged. At 84,992, the reported draft compute reservation fell from 372.75 to 333.27 MiB: only 39.48 MiB. Huihui repeated cold/warm retrieval passed. This is not a demonstrated speed improvement; its additional forced-decode attempt was interrupted once the small savings were established. No reduced-draft setting is adopted as an optimization. A subsequent Q3 run with this setting refused before prefill because the reference fitter still could not meet the 512 MiB reserve.

Parsed MTP memory fix: previous parser overwrote main KV with the last (draft) KV value. Raw logs and timing/VRAM samples are intact. Use [reparsed buffer allocations](../bench/evidence/compare-buffer-allocations.json), which sums distinct main/draft KV and recurrent/model allocation events. Compute reservation logs repeat, so compute values are last logged reservations, not total simultaneous or peak graph memory. A regression test covers this distinction.

## Preference and remaining gates

- Huihui is the user-preferred model and the strongest candidate on these three coding fixtures. The 32K MTP3 profile is the measured fast candidate. It is not a production or broad agent-quality certification.
- Huihui near-85K completed retrieval and 128-token decoding, with only a few hundred MiB device headroom. Treat it as experimental. Q3 near-85K is memory-pressure limited in this run; a failed margin is now refused unless explicitly overridden.
- Previous 128K Huihui measurements used MTP off and partial CPU placement, not the current fast profile. They do not establish MTP3 at 128K. Native full-history attention remains intact; q4/q8 KV are explicitly lossy.
- 128K/256K useful coding context, diverse long-range retrieval, tool/API conformance, independent layer/logit parity, stability and exact speculative sampling equivalence remain open.

## Evidence

- [Coding sanitized JSONL](../bench/evidence/compare-coding-32k.jsonl) and [MTP-separated summary](../bench/evidence/compare-coding-32k-summary.json).
- [Completed context probes](../bench/evidence/compare-context-mtp3-v2.jsonl) and [summary](../bench/evidence/compare-context-mtp3-v2-summary.json).
- [Cancelled pressure outcome](../bench/evidence/compare-pressure-outcome.jsonl), [draft4 probes](../bench/evidence/compare-context-draft4.jsonl), [Q3 draft4 budget gate](../bench/evidence/compare-q3-draft4-budget.jsonl).
- Each row includes both model and binary checksums, exact argv, source/fixture hashes, source snapshot, model audit where captured, seed/sampling, exact prompt/output counts, raw log path, timings and sampled memory. Repository HEAD is unborn; commit SHA is null. No commits or pushes.
- Retained coding fixture source: [QwenAtHome focused_checks.py](https://github.com/AYMNrh/QwenAtHome/blob/main/benchmarks/focused_checks.py), Git blob `4860d114b71f43954b077476bab853535ac3428f`. The AST filter is not a security sandbox.
