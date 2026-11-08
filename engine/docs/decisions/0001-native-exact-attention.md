# 0001 — Preserve native hybrid semantics

Status: accepted, 2026-11-08.

The actual GGUF architecture is qwen35. Its main network has 16 dense full-history attention layers and 48 recurrent gated-delta layers, plus a separate dense MTP layer. Treating all 65 layers as conventional KV attention would misestimate memory and misimplement inference.

The first executable uses llama.cpp as an external reference backend. QAH independently owns metadata validation, planning, fixture generation, lifecycle and telemetry. This is a reference-backed starting point, not an independent transformer implementation or a speed optimization.

f16 KV is the attention-state reference. Quantized KV is explicitly lossy, even though dense layers still attend to full history. CPU weight placement does not change attention semantics. Neither prefix eviction nor sliding windows nor RoPE overrides are enabled. Context shifting and automatic fit are disabled.

No context beyond the model's 262,144 metadata limit runs automatically. 512K needs an explicit positional-extension decision and quality experiment. Native architecture and declared context are facts about the artifact; they are not evidence of useful long-context accuracy.

Custom kernels, MTP, prefix DAG, exact host KV tiering and a standalone graph executor remain gated on baseline measurements and differential correctness. Recurrent rollback requires saved recurrent state; truncating a token list alone cannot restore it.
