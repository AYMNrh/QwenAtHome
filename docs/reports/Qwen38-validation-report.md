# Qwen3.8-27B validation report

Date: 2026-11-04. Hardware: RTX 5070 Ti 16 GB, Ryzen 7 7800X3D, 64 GB RAM.

Runtime: llama.cpp b12110 (cd959bae9), Windows CUDA 13.4. Model: Unsloth Qwen3.8-27B UD-IQ4_XS GGUF. Context allocation: 32,768 tokens. Flash Attention enabled, all GPU layers, 4-bit K/V cache, GPU sampling, one slot. No weight changes.

## Coding checks

Three unique isolated correctness checks were run against each profile. These are synthetic examples resembling coding tasks, not measurements on the user's repository. The model used greedy decoding, seed 42, and thinking disabled. Each task was measured once per profile; results are indicative, not a statistical study.

| Task | Ordinary tok/s | MTP tok/s | Editing tok/s | Functional checks |
|---|---:|---:|---:|---|
| TTL cache expiry bug | 50.9 | 130.3 | 244.3 | Passed all profiles |
| CSV multi-function feature | 50.8 | 125.1 | 102.6 | Passed all profiles |
| Lazy sorted-event merge | 50.9 | 104.3 | 92.9 | Passed all profiles |

Ordinary decoding disables speculation. MTP drafts up to three tokens. The editing profile combines MTP with an 8-token lookup key and up to 64 copied draft tokens.

Functional checks: exact TTL expiry and zero TTL; CSV delimiter propagation, escaping, line endings and input preservation; stable event ordering, laziness, object identity and empty streams. Generated code was parsed, screened for unexpected imports/capabilities, and run in separate Python processes with a timeout.

Implementations and response lengths differ between profiles. Passing these focused checks is not evidence of production readiness, comprehensive correctness, or byte-identical output. The fresh-code answer included redundant scaffolding/comments, so review remains necessary.

## Long-context retrieval: editing profile

Each input contained archive records plus three reference values placed near its beginning, middle and end. A follow-up requested the same values in a different key order. Values matched on all six requests; this is a narrow retrieval check, not broad reasoning or coding validation at depth. Some 8K replies added Markdown fences despite the JSON-only instruction.

| Actual input tokens | Phase | Cached tokens | Prompt processing s | Generation tok/s | Total request s | Minimum free VRAM MiB |
|---:|---|---:|---:|---:|---:|---:|
| 8,108 | cold | 0 | 4.86 | 114.1 | 5.29 | 549 |
| 8,192 | resumed | 8,157 | 0.19 | 67.0 | 0.92 | 529 |
| 16,299 | cold | 0 | 10.01 | 115.1 | 10.53 | 513 |
| 16,378 | resumed | 16,343 | 0.20 | 60.6 | 0.94 | 509 |
| 31,916 | cold | 0 | 22.97 | 103.2 | 23.58 | 497 |
| 31,995 | resumed | 31,960 | 0.20 | 54.3 | 1.04 | 497 |

Cold requests reported zero reused prompt tokens. Follow-ups reused nearly all previous tokens. VRAM was sampled approximately every 0.75 seconds; reported headroom is not a guarantee against shorter transient peaks or memory use by other applications. No crash or out-of-memory error occurred. Near-32K was tested at 31,916 prompt tokens, leaving room for the answer and follow-up; this is not a 32,768-token input test. Long-context checks were run on the editing profile only.

## Profiles saved

- `Start-Qwen38-General.cmd`: MTP only; preferable for fresh code and general responses in these checks.
- `Start-Qwen38.cmd`: MTP plus prompt lookup; faster on the patch that reused most source text. This profile is available as the editing alternative.

The general MTP-only profile was restored after the Flash comparison, before subsequent Q3 and Huihui experiments. Both use localhost port 8081. Run one at a time, after stopping the existing server. Both preserve default interactive thinking behavior; benchmark requests explicitly disabled thinking. Benchmark speeds therefore do not predict thinking-mode latency.

## Configuration differences

```text
Shared: --ctx-size 32768 --gpu-layers all --flash-attn on
        --cache-type-k q4_0 --cache-type-v q4_0 --backend-sampling
        --spec-draft-n-max 3
        --spec-draft-type-k q8_0 --spec-draft-type-v q8_0
General: --spec-type draft-mtp
Editing: --spec-type draft-mtp,ngram-simple
         --spec-ngram-simple-size-n 8 --spec-ngram-simple-size-m 64
```

The compressed KV cache is a memory/precision tradeoff. MTP and backend arithmetic may change exact output. DFlash2 is not active. No drivers, clocks, power limits, or user repositories were changed.



Publication note: this is a historical experiment report. Model activity statements describe that run, not the current state of a reader's machine. Raw result files are in ../../data/; portable launchers are in ../../profiles/.
