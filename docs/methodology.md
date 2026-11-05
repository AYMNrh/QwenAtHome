# Methodology and reproduction

## What each number means

- Decode tok/s: the engine's `timings.predicted_per_second`, excluding prompt processing.
- Prompt processing: `prompt_ms` / `prompt_per_second`, covering newly read tokens as reported by that engine.
- Wall time: HTTP request elapsed time when explicitly captured; it includes input processing and generation.
- Cached tokens: reported prompt reuse, not newly read input. Prefix reuse reduces repeated prefill; lookup proposes output tokens copied from context. They are distinct optimizations.
- Context allocation: the configured total window, not proof that a benchmark filled it. Prompt plus generation must fit.
- Thinking: generated reasoning can consume output tokens and time. Thinking-on results cannot be equated with thinking-off answers of different lengths.

## Coding fixtures

Three unique synthetic Python tasks: TTL expiry and zero TTL; CSV delimiter/escaping propagation without input mutation; lazy stable merging of sorted event iterables. Each has a focused executable check. Generated modules were AST-screened and run in separate Python processes with an eight-second timeout. That filter is not a security sandbox; use a disposable VM/container if executing untrusted model output.

The [retained harness](../benchmarks/focused_checks.py) uses the Python standard library. Examples, with an already-running local llama.cpp server:

```powershell
$env:BENCH_URL = 'http://127.0.0.1:8081'
$env:MODEL_ALIAS = 'Huihui-Qwen3.8-27B'
$env:BENCH_OUTPUT_DIR = 'benchmark-output'
python benchmarks/focused_checks.py my-run
$env:CONTEXT_RESULTS = 'my-context-results.json'
python benchmarks/focused_checks.py context 32000
```

This harness calls llama.cpp `/tokenize` and `/detokenize`; it is not a drop-in Strata context harness. Strata's context inputs were built with its pack's local tokenizer because those HTTP endpoints returned 404. The public harness writes results and screened modules under `BENCH_OUTPUT_DIR`; use a unique run name to avoid overwriting them. It does not launch or stop servers.

Coding requests used temperature 0, seed 42, thinking disabled, and up to 1,600 generated tokens. A failure can be a runtime error or output-cap truncation, not just slow inference. Raw JSON includes completion status, outputs, and validation errors.

## Context fixtures

Archive-like filler contained three reference values near the start, middle, and end. A follow-up requested the same values with reordered keys. JSON values were checked after extracting an object, so replies with Markdown fences could pass semantic retrieval while violating strict JSON formatting. Results say retrieval passed, not that strict structured-output compliance passed.

Near-32K cold input was 31,916 tokens; near-84K cold input was 83,916. Follow-ups reused most previous tokens. GPU memory was sampled about every 0.75 seconds; short peaks may be missed. Most context checks were one cold request and one follow-up per size.

## Statistical limits

IQ4_XS coding checks were one generation per task per profile. Flash's final short-task values are medians of three sequential rounds on a single engine; expert caches warm across rounds, and unique input prefixes prevented full prompt reuse. Q3 and Huihui were small single-request comparisons. Outputs, precision, sampling, reasoning, and context allocation differ, so no universal model ranking or guaranteed speedup follows.

No fresh GPU inference was run to prepare these public documents. Existing retained measurements were summarized and sanitized. The public code keeps the same three focused checks, rather than expanding the evaluation suite.
