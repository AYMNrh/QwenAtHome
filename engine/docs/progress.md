# Progress

## 2026-11-08 — Initial audit and implementation

- Repository was empty: unborn `master`, no tracked files, submodules, configs or baseline implementation. No user files overwritten; no commits or pushes authorized by the direct request.
- Read the execution plan in full. Implementing Phase 0 and Phase 1 first; later phases remain gated by measured evidence.
- GPU accessible: RTX 5070 Ti, 16,303 MiB reported by nvidia-smi, driver 621.14. Toolkit 12.6.85. Existing reference executable: <LOCAL_PATH>/llama-server.exe, build 12110, commit cd959bae9, CUDA sm_120 present in historical startup log.
- Located three Qwen3.8-27B GGUF weight variants. Existing reference log indicates qwen35 hybrid architecture, 64 trunk + 1 MTP, 16 full-attention and 48 recurrent layers. Independent GGUF parser and memory estimator being validated against the actual file.
- Python 3.10 Store launcher is inaccessible; Python 3.9.5 works. Implementation uses standard library only.
- RAM/CPU CIM inspection denied by host permissions; historical reference log reports 7800X3D and 64,548 MiB RAM. Current physical RAM and PCIe bandwidth must be measured separately.
- Existing ~84K / ~70 tok/s baseline is user-reported, not reproduced. 128K/256K/512K quality and speed are unmeasured.

## Milestone 1 — Executable inventory and model-specific planner

- Implemented `src/qah/model.py`: bounded little-endian GGUF v2/v3 reader, metadata and tensor directory validation, supported quantization block sizes, alignment/overlap/file-bound checks, per-layer encoded sizes and streaming SHA-256. Rejects unsupported architectures/shards/encodings instead of guessing.
- Actual IQ3_S model: 866 tensors, SHA-256 `eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19`. Metadata/tensor families agree on 64 trunk layers (16 dense/48 recurrent) plus one MTP block; metadata context limit 262,144.
- Implemented `src/qah/memory.py`, `bench/audit.py`, architecture audit, memory formulae and an ADR. Phase 0 gate passed with explicitly documented workspace/graph/placement unknowns.
- Windows `GlobalMemoryStatusEx` bypasses the unavailable CIM query without escalation: live physical RAM 67,684,352,000 bytes (64,548.8 MiB). PCIe under inference reports Gen5 x16, versus idle Gen1 x16; transfer bandwidth remains unmeasured.
- `py -3.9 -m unittest discover -s tests -v`: 3 tests pass (GGUF bounds, hybrid memory/gates, truthful summary scoring). No added dependencies.

## Milestone 2 — Reference-backed execution and benchmark harness

- Implemented isolated reference lifecycle/streaming, memory sampling, exact token-count fixtures, reproducible seeds, cold/warm/tool-prefix phases, forced-length decode probe, dependency-tracing task, JSONL schema and median/p95 summary.
- Sampling, EOS override for throughput only, lossy KV, positional limits, fit behavior, requested placement and actual backend terminal settings are recorded. New runs snapshot source/fixtures/configs because repository HEAD is still unborn.
- Initial 8K f16 smoke: needle exact-match passed, cold/warm deterministic outputs matched, but warm input-cache count was zero. Tool-prefix prototype failed strict quality; do not count it as working tool support.
- Initial throughput smoke exposed a capacity-boundary issue in the harness: reserve an additional token and reject truncated throughput results. Fixed before context probes; the original smoke's truncated decode samples are diagnostic only.
- Controlled q4_0 probes use 64 GPU layers, one trial, midpoint needle and 128 generated throughput tokens. At 8K/32K retrieval passed; code-task strict answer scoring failed (returned Python code rather than integer). Preserve failures; do not loosen scoring.
- Reference default verbosity omits allocation details. Subsequent runs explicitly request verbosity 4; earlier logs cannot establish precise tensor residency.
- A broad matrix was interrupted after one cold sample to prioritize bounded context probes. It is incomplete, not a completed benchmark.

## Long-context probe update

- Completed 84 Ki-token capacity probes: exact midpoint retrieval passed; dependency tracing failed strict scoring; forced 128-token decode completed without truncation at about 26.83 backend decode tok/s. Cold TTFT was about 81 seconds. These are single-trial, lossy-KV, partly CPU-placed reference measurements, not engine optimization claims.
- At 131,072 capacity, 130,943 prompt tokens successfully prefilled and midpoint retrieval passed exact match. TTFT about 164.97 seconds, 15 predicted tokens. Other 128K checks still running at this entry.
- Added allocation-only runs to distinguish load/warmup from prefill, sustained decode and quality. GPU gates exclude uncertain shared tensor placement, and retain the 1 GiB reserve.
- Verbose allocation evidence showed an important backend placement detail: `--n-gpu-layers 64` offloads 64/66 placement slots, with 6.23 MiB recurrent state on CPU (two recurrent layers). Placement includes the stored MTP block and output slot, even with speculation disabled. Corrected the all-trunk GPU gate to require 66 slots; earlier q4 allocation gate rows using 64 are diagnostic and superseded by final all-GPU (`99`) checks. Never infer actual residency from the requested layer number alone.

## Milestone 3 — Completed initial measurements and truth table

Done:

- 12 full context probes completed: retrieval, dependency tracing and forced 128-token decode at 8K/32K/84 Ki/128K. Needle passed at each midpoint; code task failed at every length. All revised forced decodes completed without truncation.
- 128K: exact prompt 130,943 tokens; decode TTFT 164.922 s; backend decode 22.679 tok/s for 128 forced tokens, one trial, q4_0 K/V, 64 requested placement slots (two recurrent trunk layers CPU placed). Sampled device-wide peak 15,792 MiB includes other apps. This is a measured reference probe, not validated useful 128K or an optimization.
- Three 8K f16 reference trials per task: retrieval 3/3, code 0/3, forced decode 3/3. Median forced-decode rate 52.348 tok/s; nearest-rank p95 52.665. Median TTFT 4.040 s. No comparison to the user-reported ~70 tok/s baseline is established because model/config/placement differ.
- Final frozen-source allocation run (`allocation-verified-q4.jsonl`): 128K q4 all-trunk GPU load/warmup succeeded, 256K all-trunk GPU budget refused, 512K positional limit refused. Earlier all-GPU allocation run has the same outcomes; verified run captures the final gate implementation.
- 256K q4 with 48 requested GPU slots loaded and warmed up successfully: 1,152 MiB KV CPU + 3,456 MiB KV GPU, matching 4,608 MiB predicted. Full 256K prefill/decode/quality remain untested. CPU placement includes four dense layers and fourteen recurrent layers.
- Captured detailed backend allocation logs, process/device memory, source snapshots, model/binary checksums, seed/sampling settings, JSONL and median/p95 summaries. Created `docs/benchmark-results.md` with evidence links and limitations.
- Final validation: `py -3.9 -m unittest discover -s tests -v` (3 pass); `py -3.9 -m compileall -q src bench tests` (pass); JSONL required fields/phase/status checks and supported source-snapshot hashes (pass). No dependencies, commits, pushes, custom kernels, approximate attention or positional overrides added. All owned reference processes stopped.

Blocked/unmeasured gates:

- Phase 0 passed. Phase 1 foundation is executable, but useful-context quality, long-context repeatability and real tool/agent performance gates have **not** passed. Strict code fixture failure also occurs at 8K f16; investigate task/template/reasoning configuration before attributing it to context or KV quantization.
- Full 256K tests need an explicit CPU-placement experiment and runtime budget; 512K needs an independently evaluated positional-extension strategy. Allocation alone is not support.
- Independent graph/logit parity, MTP, rollback, prefix DAG, exact host KV tiering, API/tool conformance, PCIe transfer measurement and optimizations remain unimplemented/unmeasured. No validated production hardware profiles exist.

Next:

1. Validate representative coding-agent fixtures and model template/reasoning settings, retaining strict scoring and the current failure evidence.
2. Repeat 128K at multiple needle depths/seeds with safe headroom, including feasible f16 comparisons and measured q8/q4 quality deltas.
3. Run full 256K prefill, sustained decode and quality using the measured partial CPU placement; measure host compute/transfer costs.
4. Only after baseline gates pass, implement independent forward/logit checks and recurrent snapshot/rollback semantics before replacing execution components.

## Baseline identified from QwenAtHome repository — 2026-11-08

Inspected https://github.com/AYMNrh/QwenAtHome (README, launch profiles, methodology, retained coding harness, Q3/Huihui reports and raw Q3 results). The local ENGINEatHome repository has no remote and is a separate workspace; nothing was cloned, merged, committed or pushed.

- The historical ~84K profile is **Qwen3.8-27B-UD-Q3_K_XL.gguf**, SHA-256 `8c2a45ff85e7674ca185ec8eb6cdeab0e617ed9d8018caed0b64380eb2a67a5e`, allocation **84,992** (not the 86,016 probe capacity used here).
- Published launcher: all GPU placement, q4_0 main K/V, draft-mtp up to 3 tokens, q8_0 draft K/V, batch 512/microbatch 128, backend sampling, Jinja chat template, fit on/512 MiB target, one slot. Our initial probes used a different model, disabled MTP, microbatch 512 and partial CPU placement; they do not reproduce this baseline.
- Retained raw Q3 results: short chat 67.833 tok/s with a 34-token prompt, 413 generated tokens; thinking chat 65.122 tok/s with a 74-token prompt, 512 generated tokens (hit output cap). Near-filled cold prompt 83,916 tokens: 236.022 s prefill, 39.025 decode tok/s, 237.381 s wall; resumed 84,000 tokens: 83,965 cached, 35 newly evaluated, 46.867 decode tok/s, 1.439 s wall. Both retrieval checks passed. These are historical measurements, not newly reproduced results or sustained 128-token filled-context benchmarks.
- The Huihui file we inspected matches the separate published Huihui SHA-256 exactly, but that historical profile was 32K, q8 KV and MTP. The repo records two successful edit tasks and a failing fresh-code task; its executable coding checks are more representative than our integer-only dependency fixture. They use chat completions with enable_thinking=false and up to 1,600 generated tokens.
- Next baseline work must checksum/audit Q3_K_XL and reproduce its exact 84,992-token profile before comparing a new runtime or MTP/context changes. Preserve all earlier probe results as measurements of their actual configurations. Do not interpret the ~70 tok/s short-chat figure as filled-84K speed.

Sources: [Q3 launcher](https://github.com/AYMNrh/QwenAtHome/blob/main/profiles/Start-Qwen38-Q3-85K.cmd), [Q3 report](https://github.com/AYMNrh/QwenAtHome/blob/main/docs/reports/Qwen38-Q3-85K-report.md), [raw Q3 results](https://github.com/AYMNrh/QwenAtHome/blob/main/data/Qwen38-Q3-85K-results.json), [methodology](https://github.com/AYMNrh/QwenAtHome/blob/main/docs/methodology.md).

## Matched model comparison started — user prefers abliterated Huihui

- User requested testing both Q3_K_XL and Huihui, with Huihui as the preferred model. Preference recorded; no model replacement or deployment performed.
- Added `bench/compare.py` and retained the user's published three executable coding fixtures (`bench/fixtures/upstream_focused_checks.py`, upstream blob 4860d114b71f43954b077476bab853535ac3428f). These are existing checks, not an expanded generated test suite. Generated modules are AST-screened and executed in isolated Python subprocesses with the original eight-second timeout; that screening is not a security sandbox.
- Reference adapter now supports explicit MTP depth, microbatch, GPU sampling and prefix/checkpoint settings while retaining previous defaults (MTP off, cache off, fit off). Comparison uses native Jinja chat formatting with thinking disabled, seed 42, up to 1,600 output tokens, q4 main K/V, q8 draft K/V, all GPU placement, batch 512/microbatch 128, GPU sampling, fit on/512 MiB target and original cache settings.
- Running three coding trials per model with MTP 0 and 3 at 32K capacity. Identical fixed seed is intentional for deterministic repeatability and MTP output comparisons, not a diverse task accuracy estimate. Full-prefix retrieval/decode probes are separate from short coding requests.
- Summary grouping now separates MTP depth/speculation; regression added to the existing summary test, with no extra test functions. No silent mixing of MTP-off and MTP-on speeds.

### Matched coding milestone completed

- 36 requests completed: two models, MTP depths 0/3, three existing coding checks, three repeats. Both model checksums match the published baseline. No coding prompt cache reuse (cache_n=0). All repeated outputs within each profile/task were identical, so repeats measure timing variability rather than task diversity.
- Huihui MTP3: bugfix 3/3 at median 125.94 tok/s; CSV edit 3/3 at 115.26; fresh code 3/3 at 96.92. Median HTTP task times 2.08 / 1.75 / 6.77 s respectively.
- Q3_K_XL MTP3: bugfix 3/3 at 123.86 tok/s; CSV edit 3/3 at 116.66; fresh code 0/3 (TypeError: list is not an iterator). Failed fresh outputs still report speed but are never counted as completed coding tasks.
- Without MTP, both pass edits and fail fresh code. Huihui bugfix/CSV medians 50.72/50.49 tok/s; Q3 47.35/47.97. For Huihui, the edit outputs are identical with MTP on/off, while fresh-code output differs and passes only with MTP3. Do not claim general deterministic/logit equivalence: per-layer/logit comparisons and near-tie behavior are unresolved.
- Raw results: `bench/results/compare-coding-32k.jsonl`; MTP-separated summary: `bench/results/compare-coding-32k-summary.json`. These small synthetic tasks support the user's Huihui preference, not a broad model-quality ranking.
- Long-context comparison is underway at 32,768 and 84,992 capacity, MTP3, identical q4 main/q8 draft cache configuration. Native-template midpoint retrieval and a 128-token parser-generation throughput probe are distinct tasks. An interrupted pilot accidentally used a short-answer retrieval prompt for forced decoding; excluded it and restarted with the long-code prompt (`compare-context-mtp3-v2.jsonl`).

### Comparison complete — preference retained

- Huihui MTP3 completed 32K and 84,992-capacity cold/warm retrieval plus forced 128-token parser generation. At 32K: 73.59 decode tok/s; at 84,992: 56.21 tok/s. Near-85K exact prompt was 84,735 tokens; cold retrieval took 106.67 s, warm 0.44 s. All four needle checks passed. These are single probes, not long-context statistical validation or full code-quality checks.
- Q3 MTP3 completed the same 32K checks, with 75.39 parser decode tok/s. Its near-85K prefill slowed severely; last progress was 47,616 tokens at 300.36 server-reported prefill seconds, including roughly 57 s for the last 512-token segment. Stopped the memory-pressure attempt and retained a cancelled outcome, explicitly not an OOM or completed benchmark. No full near-85K Q3 decode rate is claimed.
- Tested one targeted workspace change: draft microbatch 4 instead of 128. Actual draft reservation only fell 372.75 -> 333.27 MiB (39.48 MiB), insufficient to resolve the margin problem. Huihui cold/warm retrieval repeated successfully; remaining throughput experiment was interrupted without adopting or claiming a speed optimization.
- Added a comparison startup gate: if the reference fitter reports failure to meet its requested 512 MiB reserve, refuse before prefill unless `--allow-memory-pressure` is explicit. A fresh Q3/84,992/draft4 run produced `refused_budget`, confirming the gate. This says the profile cannot meet its reserve in this run, not that historical 84K Q3 results or other placements are impossible.
- Fixed MTP allocation parsing: main and draft KV entries previously overwrote each other. New parser preserves allocation events and sums coexisting model/KV/state buffers, while treating compute reservations as repeated/last values. One regression test added (four total test functions). Earlier raw timings/VRAM samples/logs remain intact; `bench/results/compare-buffer-allocations.json` reparses complete logs for corrected buffer accounting.
- Outcome: retain **Huihui abliterated** as preferred. MTP3 at 32K is the fastest tested candidate on these fixtures; 84,992 remains experimental with a few hundred MiB VRAM headroom. Existing 128K MTP-off/partial-CPU results remain separate. No persistent server, weights, sampling algorithm, attention mask or deployment was changed.
- Report: `docs/model-comparison.md`; exact commands in README. Model preference persisted in `configs/experiments.json`. Full 128K/256K agent quality, safe headroom, independent logit parity and general MTP output equivalence remain open.
- Final validation: `py -3.9 -m unittest discover -s tests -v` (4 pass), `py -3.9 -m compileall -q src bench tests` (pass), required JSONL fields/counts and archived-source hash checks (49 rows pass). All owned llama-server processes stopped. No commits or pushes.

## Publication package — 2026-11-08

Engine work is introduced under `engine/`, preserving existing QwenAtHome reports and profiles. Sanitized synthetic evidence is allowlisted under `engine/bench/evidence/`; private paths, full logs, original source snapshots, weights and binaries are excluded. Measurements predate this engine commit, so their original null commit SHAs remain unchanged. Four tests and compilation passed before publication.
