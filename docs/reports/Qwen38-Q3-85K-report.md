# Qwen3.8-27B Q3_K_XL / 85K report

Date: 2026-11-04. Hardware: RTX 5070 Ti 16GB, Ryzen 7 7800X3D, 64GB RAM.

## Active configuration

llama.cpp b12110 CUDA 13.4; Qwen3.8-27B-UD-Q3_K_XL GGUF (13,146,393,504 bytes). Download SHA256 verified against Hugging Face metadata. IQ4_XS and Flash files remain available; Flash is stopped.

84,992-token allocation; all GPU layers; Flash Attention; Q4_0 main K/V cache; MTP drafts up to 3 tokens with Q8_0 draft K/V; GPU sampling; batch 512 / microbatch 128; one slot. Local server: htt<LOCAL_PATH>

Launcher: Start-Qwen38-Q3-85K.cmd. The original IQ4_XS 32K launchers are preserved. Run only one server on port 8081.

## Conversational speed on the final configuration

| Mode | Decode tok/s | Output tokens | Total seconds |
|---|---:|---:|---:|
| Thinking off | 67.8 | 413 | 6.36 |
| Thinking on | 65.1 | 512 | 8.11 |

One CPU/GPU explanation request per mode, temperature 1 and seed 42. The thinking-enabled request reached its 512-token output limit, so its speed includes reasoning and is not a completed-answer quality score. Previous IQ4_XS interactive logs showed roughly 52-54 tok/s on different prompts; the new 65-68 tok/s is encouraging but is not a controlled same-prompt quantization comparison.

## Focused coding checks

Greedy decoding, thinking off, seed 42, 1,600-token output cap. Initial pass on the original 85K MTP configuration:

| Task | Decode tok/s | Result |
|---|---:|---|
| bugfix | 59.9 | Pass |
| multi_function_edit | 54.2 | Pass |
| fresh_code | 48.5 | Fail |

The fresh generator called next() on a list instead of creating an iterator. Without MTP, the same two edit checks passed and the generator failed again; generation was about 48 tok/s. A smaller-batch trial produced 114-119 tok/s on edits, but its fresh answer hit the output cap and its long-context request timed out. That trial was reverted. These small examples do not establish broad agent quality, nor prove a general quality ranking between quantizations. No Hermes end-to-end run was performed.

## Long-context validation

The original configuration (also restored as the final configuration) recovered all three markers near the start, middle and end at 83,916 input tokens, then repeated them correctly in a follow-up at 84,000 input tokens. Replies included Markdown fences despite the JSON-only instruction.

| Phase | Prompt tokens | Prompt seconds | Decode tok/s | Total seconds |
|---|---:|---:|---:|---:|
| cold | 83916 | 236.02 | 39.0 | 237.38 |
| resumed | 84000 | 0.35 | 46.9 | 1.44 |

Minimum sampled free VRAM was only 115 MiB. This is a near-full-context retrieval check, not a maximum-size input test, repeated stability test, or complex agent workflow. Leave room for generated output within the 84,992-token allocation. Other GPU applications can reduce headroom.

The smaller-batch trial initially processed faster, then slowed sharply above 60K and exceeded the 300-second HTTP timeout; the server released it at 65,024 processed tokens. GPU memory pressure was observed, but the exact paging cause was not conclusively isolated. The profile was restored to the settings that had completed retrieval; final chat requests succeeded.

## Practical conclusion

Q3_K_XL provides 2.59 times the configured context of the previous 32K setup and measured about 65-68 tok/s on short conversation requests. The full initial read near 84K took about four minutes; the cached follow-up took 1.44 seconds. The larger window fits narrowly and needs workload-specific validation before relying on long autonomous sessions. The focused fresh-code failure remains a material limitation.

Community comparison: http<LOCAL_PATH>
Model source: http<LOCAL_PATH>

Raw measurements, generated responses and validation errors: Qwen38-Q3-85K-results.json.


Publication note: this is a historical experiment report. Model activity statements describe that run, not the current state of a reader's machine. Raw result files are in ../../data/; portable launchers are in ../../profiles/.
