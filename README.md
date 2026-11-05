# QwenAtHome

Measured local Qwen inference experiments on one RTX 5070 Ti 16 GB: llama.cpp, Strata, MTP, DFlash2, prompt lookup, quantization, and context limits.

**[Open the standalone HTML documentation](docs/index.html)** by downloading the repository and opening that file locally. GitHub displays HTML source; GitHub Pages is not configured by this change. The HTML needs no server, JavaScript, external assets, or network access to read.

## Hardware and scope

- GPU: one NVIDIA GeForce RTX 5070 Ti, nominal 16 GB VRAM.
- CPU: AMD Ryzen 7 7800X3D, 8 cores / 16 threads; AVX-512 detected by Strata.
- RAM: 64 GB DDR5-6000, 2 x 32 GB.
- OS: Windows 11 Pro. Models stored on a Crucial P3 NVMe SSD.
- Measured November 4–5, 2026. No rented GPU or second GPU was benchmarked locally.

## Results at a glance

| Model and profile | Context allocation | Representative decode speed | What was actually checked |
|---|---:|---:|---|
| Qwen3.8-27B UD-IQ4_XS, ordinary | 32,768 | ~51 tok/s | 3/3 focused coding tasks passed |
| Same, MTP x3 | 32,768 | 104–130 tok/s on focused coding | 3/3 passed; a separate prose fixture was ~80 tok/s |
| Same, MTP + lookup | 32,768 | 244 tok/s on TTL patch; 638 tok/s on a separate mostly-copy edit | 3/3 focused tasks passed; high copy speed is workload-specific |
| Qwen3.8-27B UD-Q3_K_XL, MTP x3 | 84,992 | 65–68 tok/s on short conversation fixtures | 2/3 coding tasks passed; near-84K retrieval passed |
| Qwen3.8-Flash-Next IQ2_XS, Strata | 32,768 | 121 tok/s explanation median; 164–181 on successful edit tasks | 7/9 repeated coding checks passed |
| Huihui Qwen3.8-27B GSQ-RCO IQ3_S-MTP | 32,768 | 67 tok/s thinking chat; 107–113 on successful edits | 2/3 coding tasks; near-32K retrieval; one basic security review |

**These are different workloads, sample counts, cache states, and output lengths. This is an experiment log, not a controlled cross-model leaderboard. Decode speed excludes prompt processing.**

## Documentation

- [Experiment log, model inventory, and tuning sweeps](docs/experiments.md)
- [Methodology and reproducibility](docs/methodology.md)
- [Portable launch profiles and API setup](docs/setup.md)
- [External research, GPU comparisons, and untested ideas](docs/research.md)
- [Privacy and publication scope](docs/privacy.md)
- [IQ4_XS report](docs/reports/Qwen38-validation-report.md)
- [Q3_K_XL / 85K report](docs/reports/Qwen38-Q3-85K-report.md)
- [Flash / Strata report](docs/reports/QwenFlash-benchmark-report.md)
- [Huihui report](docs/reports/Huihui-Qwen38-report.md)
- [Sanitized raw measurements](data/) and [exploratory sweeps](data/sweeps/)

## What held up

MTP helped these short coding fixtures. Context lookup helped most when output copied input. Prefix caching made repeated long-context requests dramatically quicker. A loaded model and a configured context limit did not establish stable long-context performance. Fresh-code failures occurred despite good generation speeds.

The last configured profile in this record was Huihui at 32K with Q8 KV and MTP. This repository does not monitor or control a running server. It contains no model weights, inference binaries, credentials, or personal chat exports.
