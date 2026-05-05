# PIPELINE — May 2026 SOTA, Solo-Dev Edition

The 2026 post-training stack converged. This is the pipeline TemLLM uses, with citations to current best-practice sources.

---

## The Recipe (5 stages)

```
Base model (Qwen3-1.7B)
   ↓
[1] Curated SFT (500–5K examples, QLoRA)
   ↓
[2] Synthetic distillation SFT (2K–5K from open teacher)
   ↓
[3] GRPO on verifiable reward (small slice of R2E-Gym)
   ↓
[4] Hybrid-verifier inference scaling (best-of-n with execution + non-exec verifiers)
   ↓
[5] int4 quantization for on-device deployment
```

This matches the 2026 consensus: **Base → SFT → DPO/GRPO → Merge → Inference scaling**. ([Tummala 2026 post-training playbook](http://gopikrishnatummala.com/posts/mlops/modern-post-training-peft-2026/), [Red Hat / Unsloth 2026](https://developers.redhat.com/articles/2026/04/01/unsloth-and-training-hub-lightning-fast-lora-and-qlora-fine-tuning))

---

## Stage 1 — Curated SFT with QLoRA

**Why QLoRA, not full FT:**
- 4-bit quantized base, LoRA adapters trained on top
- 7B fits in 8 GB VRAM; 1.7B fits in <4 GB
- Full FT of 1.7B is also feasible at our scale but offers no edge over QLoRA at this size

**Hyperparameters (2026 default):**
- rank `r = 16` (work well across instruction tuning, style, domain)
- alpha `α = r` or `2r`
- dropout 0.05
- learning rate 2e-4 (AdamW)
- cosine schedule, 3 epochs
- packed sequences, max_seq_len 8K–32K depending on agent traces

**Data discipline (the most important part):**
- **Quality dominates: 500 clean > 5,000 noisy** ([Effloow 2026 LoRA guide](https://effloow.com/articles/llm-fine-tuning-lora-qlora-guide-2026))
- Decontaminate every example against every eval set (n-gram match + embedding similarity threshold)
- Filter agent trajectories: keep only those whose final action passed unit tests
- Format-normalise to consistent chat template with tool calls

**Tooling: Unsloth.**
- 2–5× faster than FlashAttention-2 baselines
- 80% less VRAM
- Free on Colab T4 / Kaggle T4
- ~$1–5 to fine-tune 7B on rented A100/4090 ([Spheron 2026](https://www.spheron.network/blog/how-to-fine-tune-llm-2026/))

---

## Stage 2 — Synthetic Distillation

**Why this stage exists:** the open public SFT corpus is necessarily pre-cutoff and exists in everyone's training data. Synthetic distillation against post-cutoff GitHub issues is where novelty lives.

**Pipeline:**
1. Curate ~500 fresh GitHub issues, post-base-cutoff date, in active repos with passing existing test suites
2. Wrap each in an executable environment (R2E-Gym style or SWE-Playground recipe — [arXiv 2512.12216](https://arxiv.org/html/2512.12216))
3. Run an open teacher in agent loop:
   - **DeepSeek-R1-Distill-Qwen-32B** (free, self-hostable, MIT licence)
   - Alternatives: DeepSeek-V3.1, Qwen3-Coder-Next, Qwen3.6-27B
4. Filter trajectories: only keep those whose final patch passed tests AND broke no other tests
5. Annotate each with: difficulty, tools used, # of turns, error-recovery events
6. Mix into Stage 1 mix and rerun SFT

**Cost gate:** if teacher pass-rate < 50%, the teacher prompt is wrong, not the recipe. Re-tune before scaling.

---

## Stage 3 — GRPO on Verifiable Reward

**Why GRPO, not PPO/DPO:**
- GRPO (DeepSeekMath/R1) works on a single 16GB T4 — free Colab/Kaggle GPU
- Doesn't need a separate critic model (saves VRAM)
- DPO requires preference pairs; GRPO uses scalar reward — perfect for test-pass

**Setup:**
- Environment: 200–500 R2E-Gym problems with executable test suites
- Reward function:
  - Primary (sparse): all repo tests pass → +1, else → 0
  - Optional shaping: code parses (+0.05), runs without exception (+0.05), no regressions (+0.1), patch size ≤ 200 LOC
- Curriculum: ascending difficulty (teacher-rated)
- Hyperparameters: 8 rollouts per prompt, KL penalty β=0.04, learning rate 5e-6
- Hard early-stopping: if pass-rate plateau for 2 checkpoints, stop

**Reference recipes:**
- [DeepSeekMath / GRPO paper (arXiv 2402.03300)](https://arxiv.org/abs/2402.03300)
- [Tutorial on TRL with SFT, DPO, GRPO (May 2026)](https://earezki.com/ai-news/2026-05-01-a-coding-guide-on-llm-post-training-with-trl-from-supervised-fine-tuning-to-dpo-and-grpo-reasoning/)
- [Unsloth GRPO docs](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide)

**At 1.7B, expect:** plateau early; 200–500 problems × 8 rollouts × 50 steps is achievable. Bigger budgets get more, but the marginal return at 1.7B is unclear in the literature.

---

## Stage 4 — Hybrid-Verifier Inference Scaling

**Source:** [R2E-Gym (COLM 2025)](https://r2e-gym.github.io/) — "execution-based + execution-free verifiers, weighted, gives significantly better performance than either alone."

**Pipeline:**
1. Sample n=4–8 candidate patches at inference time (temperature 0.7, top_p 0.9)
2. Run each through:
   - **Execution-based verifier:** does the patch parse? run? pass tests?
   - **Execution-free verifier:** another LLM (or rule set) scores patch quality
3. Combine: weighted sum, pick best
4. Optional: iterative refinement — best candidate gets one self-correction round

**Why this matters at 1.7B:** small models hallucinate more; ensembling at inference recovers a lot of accuracy. R2E-Gym reports +5–10 SWE-bench points from hybrid verification alone, which is ~half the gap between 1.7B and 7B.

---

## Stage 5 — Quantization for Deployment

**Goal:** ≥ 20 tok/s on M3 Pro at int4.

**Pipeline:**
1. Convert merged checkpoint (base + LoRA) to GGUF via llama.cpp
2. Quantize: Q4_K_M is the 2026 default (good quality/size tradeoff); Q5_K_M for higher quality
3. Q2_K or IQ2 for stretch goals (1.7B fits in <1GB)
4. Verify on actual M3 Pro using `llama.cpp` server or `ollama`

**Reference:** Qwen3-1.7B at Q4_K_M is ~1.1 GB and runs >40 tok/s on M-series. Easy hit.

---

## Tool Choice Cheat Sheet

| Task | Tool | Why |
|---|---|---|
| QLoRA fine-tune (single GPU) | **Unsloth** | Fastest, lowest VRAM |
| GRPO RL (single GPU) | **Unsloth GRPO** | Only thing that fits 16GB |
| YAML-driven pipelines | **Axolotl** | Composes with Unsloth |
| Reference SFT/DPO/PPO/GRPO | **TRL** | HuggingFace standard |
| Multi-turn agent RL | **SkyRL-Agent** ([arXiv 2511.16108](https://arxiv.org/html/2511.16108)) | Best 2026 multi-turn impl |
| Inference (server) | **sglang** or **vllm** | Throughput |
| Inference (Mac) | **llama.cpp** / **ollama** | M-series native |
| Eval | **SWE-bench official harness** | Standard |
| Eval (general) | **lm-evaluation-harness** | EleutherAI standard |
| Quantization | **llama.cpp GGUF** | Works on Mac |
| Tracking | **W&B (free tier)** | Standard |
| GPU rental (cheap) | **Lambda Labs spot** ($1.50/hr A100) | Cheapest reliable |
| GPU rental (free) | **Kaggle** (T4 30hr/wk) / **Colab** (T4 free) | $0 |

---

## Sources

- [Unsloth Documentation](https://unsloth.ai/docs)
- [Axolotl Docs](https://docs.axolotl.ai/)
- [Tummala "Post-Training Playbook 2026"](http://gopikrishnatummala.com/posts/mlops/modern-post-training-peft-2026/)
- [Spheron "How to Fine-Tune LLMs in 2026"](https://www.spheron.network/blog/how-to-fine-tune-llm-2026/)
- [Effloow "LoRA and QLoRA 2026"](https://effloow.com/articles/llm-fine-tuning-lora-qlora-guide-2026)
- [Red Hat × Unsloth Lightning-fast LoRA 2026](https://developers.redhat.com/articles/2026/04/01/unsloth-and-training-hub-lightning-fast-lora-and-qlora-fine-tuning)
- [TRL Post-Training Tutorial May 2026](https://earezki.com/ai-news/2026-05-01-a-coding-guide-on-llm-post-training-with-trl-from-supervised-fine-tuning-to-dpo-and-grpo-reasoning/)
- [DeepSeekMath / GRPO (2402.03300)](https://arxiv.org/abs/2402.03300)
- [R2E-Gym (2504.07164)](https://arxiv.org/abs/2504.07164)
- [SkyRL-Agent (2511.16108)](https://arxiv.org/html/2511.16108)
- [SWE-Playground (2512.12216)](https://arxiv.org/html/2512.12216)
- [Qwen3 launch blog](https://qwenlm.github.io/blog/qwen3/)
