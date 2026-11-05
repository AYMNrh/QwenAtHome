# Qwen Flash baseline — 2026-11-04

RTX 5070 Ti 16GB; Ryzen 7 7800X3D; 64GB DDR5-6000.
Strata terminal 0.2.7 / engine 0.1.52; Qwen3.8-Flash-Next IQ2_XS.
32,768 context, int8 KV, MTP spec 4, 1,500 MiB VRAM reserve; vision/thinking off; temperature 0, seed 42. Default route-tail-skip 7 remains enabled.

## Short-request results

Three sequential rounds on one running engine; medians below are engine decode speed, excluding prompt processing. Unique run prefixes avoid full prompt reuse; expert caches warm across rounds.

| Task | Median tok/s | Range | Checks passed | Median total seconds |
|---|---:|---:|---:|---:|
| TTL cache bug fix | 163.8 | 112.3–171.3 | 3/3 | 1.94 |
| CSV module edit | 180.9 | 146.2–183.8 | 3/3 | 1.51 |
| Fresh lazy merge generator | 160.3 | 156.5–167.9 | 1/3 | 1.43 |
| Arithmetic / factual JSON | 121.5 | 101.6–122.3 | 3/3 | 0.77 |
| CPU/GPU explanation | 120.6 | 90.7–125.8 | Not scored | 2.29 |

Coding passed 7/9 focused checks. Two fresh-code answers called next() on a list instead of converting it to an iterator. Their speeds are included above and do not imply correct code. Tests are three small tasks, not a broad coding-agent evaluation. Generated code was checked and run locally; no Hermes tool-use workflow was evaluated.

## Long-context retrieval

One request plus cached follow-up at each size; all six recovered the three markers at the beginning, middle and end. This tests retrieval, not complex long-context reasoning.

| Actual prompt tokens | Phase | Total seconds | Prompt seconds | Decode tok/s | Result |
|---:|---|---:|---:|---:|---|
| 8108 | cold | 3.49 | 2.94 | 88.3 | Pass |
| 8187 | resumed | 0.74 | 0.22 | 89.7 | Pass |
| 16299 | cold | 5.62 | 5.27 | 131.8 | Pass |
| 16378 | resumed | 0.59 | 0.19 | 116.3 | Pass |
| 31916 | cold | 10.69 | 10.36 | 149.2 | Pass |
| 31995 | resumed | 0.58 | 0.19 | 122.6 | Pass |

Minimum sampled free VRAM: 1046 MiB. Health endpoint remained OK after testing.

## Interpretation

This baseline reaches roughly 120 tok/s for everyday explanations and 164–181 tok/s for the two successful coding-edit tasks. Correctness remains the limiting factor for fresh code. Short outputs and MTP acceptance make speed workload-dependent; these results do not establish sustained 200+ tok/s performance.

No upgrade was performed. Engine 0.1.56 has not been measured on this machine, so these results cannot decide whether upgrading improves performance. Flash was running at the end of that baseline; subsequent experiments switched models.

The earlier default-reserve trial is excluded from these medians. Raw responses, timings and validation errors are in QwenFlash-benchmark-results.json.

## Follow-up context verification

A 65,536-context launch was attempted after the baseline. It reached ready, but the engine logged only 1.3 GiB of available Windows commit against 2.0 GiB of planned host allocations (plus a desired safety reserve). No 64K retrieval request was submitted. Loading successfully does not establish safe operation at that context. The saved Flash preset was returned to 32,768 context. Larger context remains unvalidated; Windows commit headroom needs attention before retrying.

Hermes supports automatic context compaction according to its official context-management documentation: http<LOCAL_PATH>


Publication note: this is a historical experiment report. Model activity statements describe that run, not the current state of a reader's machine. Raw result files are in ../../data/; portable launchers are in ../../profiles/.
