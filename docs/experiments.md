# Experiments and retained evidence

## Model inventory

| Artifact | File size, decimal bytes | Runtime / role |
|---|---:|---|
| Qwen3.8-27B-UD-IQ4_XS.gguf | 14,252,845,984 | llama.cpp target |
| Qwen3.8-27B-UD-Q3_K_XL.gguf | 13,146,393,504 | llama.cpp target |
| Qwen3.8-27B-DFlash2-Q4_K_M.gguf | 1,143,006,816 | optional speculative draft |
| Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf | 12,120,016,416 | llama.cpp target with embedded MTP |
| Qwen3.8-Flash-Next GSQ-RCO IQ2_XS shards | 39,225,954,592 + 28,800,138,432 | Strata native pack; separate prepared MTP files |

File size is not resident VRAM or RAM use. Flash's expert caching and lookup tables differ from the dense 27B models. GGUF contains weights and metadata; the engine determines execution and memory management.

The Q3 target SHA256 is `8c2a45ff85e7674ca185ec8eb6cdeab0e617ed9d8018caed0b64380eb2a67a5e`. Huihui is `eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19`. Downloads were verified during setup; checksums identify artifacts, not quality.

## Sequence of experiments

1. Earlier Qwen3.6-35B-A3B / small-VRAM exploration was discussed. No comparable retained results support a benchmark table for it; do not treat the early 8 GB discussion as the final machine specification.
2. Installed official llama.cpp b12110 (`cd959bae9`), Windows CUDA 13.4, and Qwen3.8-27B UD-IQ4_XS.
3. Compared ordinary decoding, MTP depths 1/3/5, full GPU offload, and Q4 main KV. Tested DFlash2 and MTP plus ngram lookup.
4. Validated three focused coding tasks and beginning/middle/end retrieval near 8K, 16K, and 32K. Saved separate general and editing profiles.
5. Downloaded/prepared Flash IQ2_XS for Strata terminal 0.2.7 / engine 0.1.52. Stopped the other engine before loading it. Closing a large competing application freed RAM before measurement; concurrent application load materially affected fit.
6. Increased Strata's VRAM reserve to 1,500 MiB, then ran three coding rounds, everyday fixtures, and context retrieval. The initial low-headroom trial is retained separately and excluded from final medians.
7. Attempted Flash at 64K. It reached ready but warned of 1.3 GiB Windows commit headroom versus 2.0 GiB planned allocations plus reserve. No 64K retrieval was submitted. Restored 32K. No page-file change was made.
8. Returned to dense 27B, then downloaded Q3_K_XL and allocated 84,992 context. Near-84K retrieval passed but took 237.38 seconds cold and 1.44 seconds resumed; sampled VRAM headroom fell to 115 MiB.
9. Disabled MTP at 85K: short generation was about 48 tok/s. Tried main microbatch 64 / draft microbatch 16: faster short edits (114–119 tok/s), but long prefill slowed above 60K and hit the 300-second HTTP timeout. Server released at 65,024 processed tokens. Reverted to microbatch 128; final chat measured 67.8 off / 65.1 on. Exact paging cause was not conclusively isolated.
10. Downloaded Huihui GSQ-RCO IQ3_S-MTP, verified SHA256, and ran 32K with Q8 main and draft KV. Chat completed at 67.4 tok/s; two edits passed; the fresh generator failed; near-32K retrieval passed with 860 MiB minimum sampled free VRAM.

## Exploratory IQ4_XS sweep

Two short fixtures, each capped at 256 generated tokens: interval-merging code plus explanation, and memory-bandwidth prose. These are ungraded exploratory generations, not the three functional coding checks. Historical sweep files do not capture every launch argument; use them as evidence of the recorded runs, not perfectly controlled ablations.

| Recorded run | Code fixture tok/s | Prose fixture tok/s |
|---|---:|---:|
| Baseline | 50.4 | 50.4 |
| MTP disabled, later run | 50.9 | 50.9 |
| MTP 1 / full-GPU record | 81.2 | 71.7 |
| MTP 3 / full-GPU record | 110.8 | 79.2 |
| MTP 3 / Q4 KV record | 114.1 | 80.4 |
| MTP 5 | 98.1 | 58.6 |
| DFlash2 | 105.7 | 48.6 |

The `mtp1` and `mtp1-fullgpu` records duplicate the same timing values, so they are not independent repetitions. MTP 5 did not improve these fixtures. DFlash2 used draft depth 7, Q8 draft cache, draft microbatch 32, and the Q4_K_M draft file; its results do not generalize to every DFlash2 implementation.

## Lookup and copy-heavy edits

The saved mostly-copy edit produced 703 tokens: lookup recorded 638.1 decode tok/s with `exact_edit=true`, versus 134.5 with DFlash2. The lookup prompt took 645 ms and generation 1,100 ms; 703 / 1.745 seconds is about 403 output tokens/s including engine prompt time, before HTTP overhead. A smaller copy fixture recorded MTP 131.0 and DFlash2 137.1 tok/s.

These are small synthetic fixtures, not sustained repository-agent runs. A previously mentioned higher repeat was not separately retained in the published measurements; 638.1 is the auditable saved lookup result. A copied output at hundreds of tokens/s does not establish fresh-code or conversation speed.

## What was not established

- No end-to-end Hermes coding or cybersecurity-agent benchmark.
- No verified refusal-rate evaluation of Huihui.
- No local Strata 0.1.56 upgrade, Flash IQ3_S benchmark, or `--kv-grow` A/B.
- No long-context reliability guarantee from a single successful needle lookup.
- No advanced cybersecurity capability result: the Huihui review was a synthetic SQL-injection / XSS example. It found both core issues, added unwanted Markdown fences, and overstated some SQL impact.
- No local 3090, 4090, 5090, DGX Spark, or RTX PRO 6000 result. Those appeared only in external research.
