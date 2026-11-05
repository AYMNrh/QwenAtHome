# External research — not local measurements

These sources were reviewed in the session. Reported results are attributed to their publishers and are not promises for the test machine. Source pages can change after the November 2026 review.

## GPUs

| Hardware appearing in research | Context | Status here |
|---|---|---|
| RTX 5070 Ti 16GB + 64GB RAM | Strata Flash IQ3_S screenshot, engine 0.1.56, 200K configured | External only: 94.7 tok/s mean vs 84.7 default; later rerun 87.8; actual-work claim ~85 |
| RTX 3090 24GB | HyperQwen patched vLLM | External only: ~133 chat / ~382 reproducing a 25K document in the original post |
| RTX PRO 6000 Blackwell 96GB | HauhauCS FastMTP | External only; large-VRAM reference hardware |
| DGX Spark | TensorFold + DFlash2 screenshot | External only; reported ~400 on mostly-copy edits, ~96 fresh code, ~41 summary |
| RTX 5080 16GB | Strata engine .54 vs .56 report | External regression report, not a local upgrade A/B |

The Strata screenshot's 200K was configured capacity, while visible requests were around 16K and current cached context was 428 tokens. It does not demonstrate 95 tok/s at a filled 200K window. The screenshot also explicitly warned that the 87.8 rerun differed from the 94.7 group mean by more than estimated run noise. Screenshots and social profiles are not republished here.

## Strata KV growth and upgrade

[`--kv-grow`](https://github.com/Niko1221/Strata/blob/main/docs/DETAILS.md#memory-modes) allocates physical KV as needed, letting expert cache use the rest at short contexts. It needs a compatible single-GPU mode, expert profile, all experts in RAM, and full GPU KV rather than KV streaming. It is not a generic llama.cpp flag. Long-context growth can trade away expert cache and change performance; a larger configured window alone is not validation.

The local baseline was engine 0.1.52. Version [0.2.10](https://github.com/Niko1221/Strata/releases/tag/v0.2.10) and engine 0.1.56 were researched, but not installed or benchmarked. A [5080 Windows slowdown report](https://github.com/Niko1221/Strata/issues/5115) motivated retaining a baseline; it does not prove every newer version is slower. A [KV-grow / prefill interaction report](https://github.com/Niko1221/Strata/issues/2310) illustrates why a configured large context still needs testing.

## HyperQwen: correction to a circulated summary

The original creator's project is [syv-ai/HyperQwen](https://github.com/syv-ai/HyperQwen), formerly qwen38-27b-rtx3090. It patches **vLLM**, not llama.cpp. TeksEdge amplified the result; the [original developer post](https://www.reddit.com/r/LocalLLaMA/comments/1vtup5s/i_pushed_qwen3827b_to_381_tps_for_a_single/) described ~133 tok/s chat, ~382 while reproducing context, 16-token verification with about 15 accepted in a favorable workload, and important long-context tradeoffs/corrections.

Lookup and prefix caching are distinct: lookup proposes output tokens from context; prefix caching avoids reprocessing input. The recipe also changes quantization and kernels; it is not just a flag that makes an existing GGUF 4.6 times faster. The published 24GB preparation is not a demonstrated fit on this 16GB setup. No HyperQwen download, conversion, installation, or benchmark was performed locally.

## Uncensored 27B candidates

| Repository | Relevant files | What was established |
|---|---|---|
| [Huihui](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF) | GSQ-RCO-IQ3_S-mtp ~12.1 GB | Downloaded and tested locally; see its report |
| [HauhauCS Aggressive](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF) | IQ3_M 12.79 GB; IQ3_XS 12.18 GB; FastMTP sidecar 903 MB | Researched only. Embedded MTP uses normal compatible llama.cpp; FastMTP requires its patch. Q3_K_P reference gains: +20.5% document / +8.8% reasoning vs embedded depth-2 profile on 96GB hardware |
| [Blackfrost](https://huggingface.co/Blackfrost-AI/Qwen3.8-27B-ABLITERATED-GGUF) | Q3_K_S 12.3 GB; Q3_K_M 13.5 GB | Researched only; embedded MTP; optional larger DFlash2 sidecar |

File sizes exclude runtime cache/buffers. Fewer refusals do not establish stronger cybersecurity or coding capability. The candidate list is not a comparable cybersecurity benchmark; reported refusal scores use different prompts and evaluation methods. HauhauCS itself recommends a Balanced variant, when available, over Aggressive for reliability-critical long-context agent work.

## Other useful sources

- [Unsloth Qwen3.8-27B GGUFs](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
- [5070 Ti community benchmark entries](https://llm-bench.io/hardware/rtx-5070-ti): Q3_K_XL 68–75 tok/s around 85K configured context; matching IQ4_XS entry 46.8 tok/s. Different runs and settings, not a same-machine controlled comparison.
- [Chimolog Strata guide](https://chimolog.co/strata-guide/): Flash IQ3_S and a DSH agent interface with 256K configured context. Its Opus-level quality comparisons are the author's assessment, not independently reproduced here.
- [Earlier 5070 Ti / 5900X Flash results](https://github.com/Niko1221/Strata/blob/main/bench/results/2026-10-06-community-rtx5070ti-5900x/README.md): external model/engine configuration, not a local result.
