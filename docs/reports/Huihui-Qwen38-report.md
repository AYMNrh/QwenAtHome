# Huihui Qwen3.8-27B installation and checks

Date: 2026-11-05. RTX 5070 Ti 16GB, Ryzen 7 7800X3D, 64GB RAM.

## Installed configuration

File: Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf (12,120,016,416 bytes). Size and SHA256 verified against repository metadata.
SHA256: eea0638e283433e27b0edbd409b552be467a75ecc777d91c51db554c0a644c19

llama.cpp b12110, CUDA 13.4; full GPU layers; Flash Attention; MTP up to 3 drafted tokens; 32,768 context; Q8_0 main and draft KV caches; GPU sampling; batch 512, microbatch 128.

Model alias: Huihui-Qwen3.8-27B. Local UI: htt<LOCAL_PATH>

The previous Q3_K_XL server was stopped. Its model and 85K launcher, the IQ4_XS models/launchers and Flash files remain intact. Only one server should use port 8081. No custom runtime patches or FastMTP sidecar are used.

## Measured generation

| Task | Decode tok/s | Result |
|---|---:|---|
| bugfix | 113.3 | Pass |
| multi_function_edit | 106.7 | Pass |
| fresh_code | 91.2 | Fail |
| chat | 67.4 | Completed; thinking enabled |
| security_review | 97.4 | Core findings correct; manual review |

One request per task, not repeated statistical benchmarks. Coding used temperature 0, seed 42, thinking disabled, and the same three focused executable checks as earlier profiles. Both edits passed. The fresh generator failed by calling next() on a list instead of creating an iterator. Chat used temperature 1, seed 42, thinking enabled, and completed in 6.96 seconds (418 total generated tokens including reasoning).

The security check reviewed a synthetic SELECT query constructed with an f-string and an unescaped HTML response. It correctly identified CWE-89 SQL injection and CWE-79 XSS, recommending parameterized queries and context-appropriate HTML escaping. No generated commands were executed. The response added Markdown fences despite a JSON-only instruction and overstated possible SQL modification/deletion impact for this particular SELECT example. This is one basic vulnerability review, not proof of advanced cybersecurity ability, tool-use reliability or a measured refusal rate.

## Near-32K context

| Phase | Input tokens | Total seconds | Decode tok/s | Result |
|---|---:|---:|---:|---|
| cold | 31916 | 28.02 | 81.7 | Pass |
| resumed | 32000 | 0.84 | 90.6 | Pass |

Both requests recovered the markers near the beginning, middle and end. Minimum sampled free VRAM: 860 MiB. Replies included Markdown fences. This is a retrieval check, not an end-to-end long-running agent evaluation. Higher contexts were not tested for this model.

## Takeaway

At the end of this experiment, the selected uncensored model was operational, with roughly 67 tok/s on the short thinking-mode chat request, 97 tok/s on the basic security review, and 107-113 tok/s on the two successful coding edits. Fresh-code correctness remains a limitation. Start at this verified 32K profile; the prior 85K result belongs to a different model and cache configuration.

Source: http<LOCAL_PATH>


Publication note: this is a historical experiment report. Model activity statements describe that run, not the current state of a reader's machine. Raw result files are in ../../data/; portable launchers are in ../../profiles/.
