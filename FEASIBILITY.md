# FEASIBILITY — What an Individual Can Actually Build

This document maps every realistic path from the thesis to a working artifact, ordered from cheapest-and-most-feasible to most-ambitious. Costs are 2025–2026 cloud GPU prices, single-builder budgets.

---

## TL;DR — recommended starting path

**Distill DeepSeek-R1 (or Qwen2.5-Math-72B-Instruct) onto Qwen2.5-Math-7B-Base, on a custom curated math+science corpus. Budget: $500–$5,000. Time: 2–6 weeks. Skill: intermediate ML engineering.** This is the path that has the highest evidence base (rStar-Math, AceMath, Phi-4-mini-reasoning all use variants), the lowest cost, and the clearest evaluation surface. Anything more ambitious requires deciding what TemLLM uniquely contributes — see `OPEN_QUESTIONS.md`.

---

## Path A — LoRA fine-tune of an existing reasoner (lowest cost, lowest novelty)

- **Goal:** Add a TemLLM "voice" or task focus to an existing strong reasoning model. Not a research result — a product layer.
- **Base:** Qwen2.5-Math-7B-Instruct, DeepSeek-R1-Distill-Qwen-7B, Phi-4-reasoning, or Llama-3.1-8B-Instruct.
- **Training:** LoRA / QLoRA, 1–4 epochs on 10K–100K curated SFT examples.
- **Hardware:** Single A100 80GB or H100. Or a 4090 with QLoRA at 4-bit.
- **Cost:** **$50–$500** for compute. Datasets free.
- **Time:** 1–3 days of training, 1–2 weeks of dataset curation.
- **Tooling:** Axolotl, llama-factory, Unsloth, TRL.
- **Honest verdict:** **This is fine-tuning, not research.** Useful as a v0 to learn the stack and shake out evaluation infrastructure before committing to anything bigger.

## Path B — Continued pretraining on curated corpus (recommended low-budget research)

- **Goal:** Test a real version of "shift the data distribution toward high-IQ" without paying full pretrain cost.
- **Base:** Qwen2.5-1.5B-Base or Qwen2.5-7B-Base (both are unusually good open base models with permissive licenses).
- **Corpus:** mix of OpenWebMath (14.7B) + MathPile (9.5B) + ProofPile-II (55B) + arXiv subset + selected Project Gutenberg + Cosmopedia (25B). ~50–100B tokens.
- **Training:** 1–2 epochs on the curated mix; standard cross-entropy.
- **Hardware:** 8×A100 or 8×H100 cluster (rented).
- **Cost:** **$2,000–$15,000** depending on scale and duration.
- **Time:** 1–4 weeks of training, 4–8 weeks of corpus engineering and evaluation.
- **Tooling:** Megatron-LM, Megatron-DeepSpeed, GPT-NeoX, or Hugging Face's `nanotron`.
- **Risk:** continued pretraining can degrade the base model's general abilities (alignment tax). Mitigate by mixing 33% curated + 67% diverse-but-filtered, per EMNLP 2025 finding.
- **Verdict:** **Highest evidence-to-cost ratio for a real result.** This is where TemLLM should focus its first compute budget if it wants to learn something the field doesn't already know.

## Path C — Distillation from a frontier reasoner (recommended for benchmark wins)

- **Goal:** Reproduce the rStar-Math / Phi-4-mini-reasoning recipe.
- **Steps:**
  1. Generate 1M+ synthetic problems + verified reasoning traces using DeepSeek-R1, GPT-4o, or Claude as teacher. Filter for verifier-passed traces.
  2. SFT base model (Qwen2.5-Math-7B-Base) on traces.
  3. Optionally RL with verifiable rewards (GRPO, DPO) on math + code.
- **Cost:**
  - Teacher inference: $200–$2,000 depending on volume and provider.
  - SFT compute: $200–$1,000 on 8×A100 for 1–2 days.
  - Optional RL: $1,000–$5,000.
  - **Total: $500–$8,000.**
- **Time:** 4–10 weeks.
- **Tooling:** TRL, OpenRLHF, vllm/sglang for fast teacher inference.
- **Verdict:** **Highest-probability path to "look at this small model beating GPT-4o on AIME"** demos. Lowest novelty — you are walking a well-trodden recipe.

## Path D — Pretrain a small model from scratch (research-grade ambition)

- **Goal:** A model whose every weight was shaped by the TemLLM corpus.
- **Scale:** 0.5B–4B params, 100B–1T tokens.
- **Cost (cloud H100s at ~$2/hour):**
  - 1B model on 100B tokens: **~$10,000–$30,000**.
  - 4B model on 1T tokens: **~$300,000–$1,000,000**.
- **Time:** 3–12 months of focused engineering and training.
- **Tooling:** Megatron-LM, llm.foundry (Mosaic/Databricks), nanotron, or for very small experiments nanoGPT / llm.c.
- **Failure modes:**
  - Single-builder pretrain runs almost always have data-pipeline bugs that surface only after weeks of training.
  - Hyperparameter search at this scale is its own research project.
  - Without diverse data, the model's general capability will be worse than open baselines — see `CHALLENGE.md`.
- **Verdict:** **Do not start here.** Only attempt if Paths A–C produced a finding interesting enough to justify a from-scratch validation, AND a budget commitment exists.

## Path E — Pretrain a competitive 7B+ model (industry-grade)

- Out of single-builder budget. **$1M–$10M+** in compute, plus a team.
- The right move if TemLLM somehow produces a finding that justifies a real lab. Not a v0.

---

## Datasets you can compose without training a single token of your own

| Dataset | Tokens | Domain | License | URL |
|---|---|---|---|---|
| FineWeb-Edu | 1.3T | Filtered educational web | ODC-By | https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu |
| OpenWebMath | 14.7B | Math from web (LaTeX-aware) | ODC-By | https://huggingface.co/datasets/open-web-math/open-web-math |
| MathPile | 9.5B | Math books + arXiv + ProofWiki | CC-BY-NC-SA | https://huggingface.co/datasets/GAIR/MathPile |
| ProofPile-II | 55B | Theorem proving + arXiv | varies | https://huggingface.co/datasets/EleutherAI/proof-pile-2 |
| Cosmopedia | 25B | Open synthetic textbooks | Apache-2.0 | https://huggingface.co/datasets/HuggingFaceTB/cosmopedia |
| OpenMathInstruct-2 | 14M problems | Math SFT | CC-BY-4.0 | https://huggingface.co/datasets/nvidia/OpenMathInstruct-2 |
| MetaMathQA | 395K | Math SFT | MIT | https://huggingface.co/datasets/meta-math/MetaMathQA |
| Llama-Nemotron-Post-Training | 30M | Reasoning SFT/RL | varies | https://huggingface.co/datasets/nvidia/Llama-Nemotron-Post-Training-Dataset-v1 |
| Tulu-3-SFT-Mixture | 939K | General SFT | ODC-By | https://huggingface.co/datasets/allenai/tulu-3-sft-mixture |

**You probably do not need to scrape anything to start.** You need to *select* and *mix*.

---

## Tooling — current best-in-class

| Layer | Tools | Notes |
|---|---|---|
| Tokenization | tiktoken, `transformers` AutoTokenizer | Reuse existing tokenizers (Qwen, Llama-3) |
| Pretraining | Megatron-LM, nanotron (HF), llm.foundry, GPT-NeoX | nanotron is most ergonomic for <10B |
| Toy pretraining | nanoGPT, llm.c, picotron | Pedagogy / tiny-scale only |
| SFT | TRL, Axolotl, llama-factory, Unsloth | Axolotl most flexible; Unsloth fastest at small scale |
| RL | TRL (PPO/DPO/GRPO), OpenRLHF, verl | OpenRLHF for production-grade |
| Inference | vllm, sglang, TensorRT-LLM | sglang best for batched reasoning traces |
| Eval | lm-evaluation-harness (EleutherAI), simple-evals (OpenAI), bigcode-eval, MATH/AIME runners | lm-eval-harness is the standard |

---

## Hardware reality check

- **Local development (Mac M-series):** Fine for tokenizer engineering, dataset curation, evaluation harness. **Useless for actual training of anything but toys.** You will rent GPUs.
- **Cloud GPU rentals (cheap):** vast.ai, Lambda Labs, RunPod. Single H100 at ~$2/hr; 8×H100 at ~$16–$20/hr. Spot pricing 30–60% off but with preemption risk.
- **Cloud GPU rentals (reliable):** Together, Modal, Anyscale, Coreweave. Higher prices, fewer surprises.
- **Free credits:** AWS Activate, Google Cloud, Lambda often have research credits. Worth applying early.

---

## What TemLLM should NOT do at v0

- Build a custom tokenizer. Reuse Qwen or Llama-3.
- Pretrain from scratch.
- Pick "all of intelligence" as the target.
- Compare to GPT-4 on Arena. (You will lose; it doesn't tell you anything.)
- Skip evaluation infrastructure. Build it before training anything.

---

## Recommended v0 plan

1. **Decide the axis.** Math? Theorem proving? Code review? Clinical reasoning? Physics derivations? Pick one — see `OPEN_QUESTIONS.md`.
2. **Build the eval harness first.** lm-evaluation-harness + a few private holdout sets the model has not seen. **No training before eval.**
3. **Run Path A (LoRA fine-tune) on a strong existing model** to shake out the eval and tooling.
4. **Run Path B (continued pretrain) or Path C (distillation)** as the actual research run. Pick one based on whether you want to test the *data* hypothesis (B) or get the *strongest model* (C).
5. **Iterate on data composition,** not on architecture. Architecture has been solved. Data has not.
