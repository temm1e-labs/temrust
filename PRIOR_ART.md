# PRIOR ART — What Has Already Been Built (2022–2026)

The thesis is **not new**. It has been the explicit research program of multiple frontier labs for three years. Anything TemLLM does must be positioned against this body of work.

---

## §1. Microsoft Phi series — the canonical "textbook curation" line

| Model | Params | Tokens | Headline | Date |
|---|---|---|---|---|
| Phi-1 | 1.3B | 7B (6B web + 1B synth) | 50.6% HumanEval; beat models 10× larger on code | Jun 2023 |
| Phi-1.5 | 1.3B | ~30B | Reasoning matched 5–10× larger | Sep 2023 |
| Phi-2 | 2.7B | 1.4T | Beat Llama-2-70B on multi-step reasoning | Dec 2023 |
| Phi-3-mini | 3.8B | 3.3T | 68.8 MMLU = Mixtral 8×7B | Apr 2024 |
| Phi-3-medium | 14B | 4.8T | 78 MMLU, MT-bench 8.9 | 2024 |
| **Phi-4** | **14B** | **9.8T** | **MMLU 84.8 / MATH 80.4 / GPQA-D 56.1 (beats GPT-4o 50.6)** | Dec 2024 |
| Phi-4-mini | 3.8B | — | Matches 2× larger on math/code | Feb 2025 |
| **Phi-4-reasoning / -plus** | **14B** | — | **AIME 2025 77.7%; beats DeepSeek-R1-Distill-70B** | Apr 2025 |
| Phi-4-mini-reasoning | 3.8B | DeepSeek-R1 synth (1M+ math) | Comparable to o1-mini on Math-500 + GPQA-D | Apr 2025 |

Key papers:
- "Textbooks Are All You Need" (Phi-1): https://arxiv.org/abs/2306.11644
- "Textbooks Are All You Need II" (Phi-1.5): https://arxiv.org/abs/2309.05463
- Phi-3 Technical Report: https://arxiv.org/abs/2404.14219
- Phi-4 Technical Report: https://arxiv.org/abs/2412.08905
- Phi-4-reasoning Technical Report: https://arxiv.org/abs/2504.21318

**Recipe in one paragraph:** filter web aggressively → generate synthetic textbooks/exercises with a frontier teacher → mix synthetic with filtered web → instruction-tune on more synthetic data → optionally RL with verifiable reward → optionally distill explicit reasoning traces. Across four generations the recipe scales cleanly.

---

## §2. Math/science specialists that beat 10–100× larger generalists

| Model | Params | Result | Year |
|---|---|---|---|
| Minerva | 540B | 50.3 MATH, 78.5 GSM8K — original arXiv pretrain | 2022 |
| Llemma | 7B / 34B | First open base with in-context theorem proving | 2023 |
| **DeepSeekMath** | 7B | **51.7 MATH, 88.2 GSM8K** — beats every open 7B–70B | 2024 |
| **Qwen2.5-Math** | 7B | **91.6 GSM8K, 55.4 MATH — beats Llama-3.1-405B (89.0 / 53.8)** | Sep 2024 |
| **rStar-Math** | 7B (Qwen base) | MCTS+PRM lifts to **90.0 MATH**, AIME 53.3% — top 20% of HS olympiad | Jan 2025 |
| **DeepSeek-R1-Distill-Qwen-1.5B** | 1.5B | **Beats GPT-4o + Claude-3.5-Sonnet on AIME (28.9) and MATH-500 (83.9)** | Jan 2025 |
| DeepSeek-R1-Distill-Qwen-7B | 7B | AIME 55.5 / MATH-500 92.8 / GPQA-D 49.1 | Jan 2025 |
| AceMath-RL-Nemotron-7B | 7B | AIME 2024 69.0% — beats o3-mini (low) and o1-mini | 2025 |
| Skywork-OR1 | 7B / 32B | 32B beats DeepSeek-R1 on AIME24 (82.2) and AIME25 (73.3) | May 2025 |

Papers:
- DeepSeekMath / GRPO: https://arxiv.org/abs/2402.03300
- Llemma: https://arxiv.org/abs/2310.10631
- rStar-Math: https://arxiv.org/abs/2501.04519
- DeepSeek-R1: https://arxiv.org/html/2501.12948v1
- Qwen2.5-Math: https://arxiv.org/abs/2409.12122

**Pattern:** narrow domain + curated corpus + RL on verifiable reward + distillation from a frontier teacher → small model parity (or victory) over generalist giants, **on the target domain**.

---

## §3. Scaling laws — Chinchilla and after

- **Chinchilla** (Hoffmann et al., DeepMind, 2022): compute-optimal at ~20:1 tokens-per-parameter. https://arxiv.org/abs/2203.15556
- **Beyond Chinchilla-Optimal** (Sardana et al., ICML 2024): when inference cost is included, optimum shifts dramatically — train *smaller* models on *more* tokens. Validated at ratios up to ~10,000:1. https://arxiv.org/abs/2401.00448
- **Llama-3 8B**: trained on **15T tokens**, ratio ~1875:1 (~100× past Chinchilla-optimal). Loss kept dropping.
- **Qwen-2.5**: 18T tokens. **DeepSeek-V3**: 14.8T.

**Lesson:** "small + heavily trained on quality data" is now the consensus frontier recipe. The thesis aligns with this trend in the *small* and *quality* dimensions; it diverges in the *narrow* dimension.

---

## §4. Data curation pipelines (open-source machinery)

| Pipeline | Size | Approach | Year |
|---|---|---|---|
| The Pile (EleutherAI) | 340B | 22 curated sources | 2020 |
| RefinedWeb (Falcon) | 500B | Aggressive web filtering | 2023 |
| RedPajama-V2 | 30T | Largest open with quality signals | 2023–24 |
| Dolma (AI2) | ~3T | Open, audited | 2023 |
| **FineWeb-Edu** | **1.3T** | Llama-3-70B-scored educational classifier; **MMLU 33→37, ARC 46→57** | Jun 2024 |
| OpenWebMath | 14.7B | Math-aware HTML/LaTeX extraction | 2024 |
| MathPile | 9.5B | Textbook + arXiv + ProofWiki + StackExchange | 2024 |
| ProofPile-II | 55B | Theorem-proving + arXiv math (used by Llemma) | 2023 |
| Cosmopedia (HF) | 25B | Open synthetic textbook corpus | 2024 |
| DSIR | — | n-gram importance resampling for selection | 2023 |
| DoReMi | — | Domain reweighting via small proxy | 2023 |

URLs:
- FineWeb-Edu: https://arxiv.org/abs/2406.17557
- OpenWebMath: https://arxiv.org/abs/2310.06786
- MathPile: https://gair-nlp.github.io/MathPile/
- DSIR: https://arxiv.org/abs/2302.03169
- DoReMi: https://arxiv.org/abs/2305.10429

**Lesson:** if TemLLM goes ahead, we don't curate from scratch — we compose from these.

---

## §5. Synthetic data scaling — the decisive lever

- **Phi-1 → Phi-4 line**: production-grade demonstration that synthetic textbooks + filtered web > pure web at small scale.
- **Self-Instruct / Alpaca / Humpback**: instruction-data bootstrapping. https://arxiv.org/abs/2308.06259
- **rStar-Math**: synthesizes verified MCTS reasoning trajectories for self-evolution.
- **Phi-4-mini-reasoning**: trained **exclusively** on >1M synthetic math problems generated by DeepSeek-R1.
- **BeyondWeb (DatologyAI, 2025)**: a **3B** model on BeyondWeb beats **8B** baselines like Cosmopedia. https://www.datologyai.com/blog/beyondweb
- **Demystifying Synthetic Data in LLM Pre-training** (EMNLP 2025): systematic scaling laws; finds **~33% synthetic + 67% filtered web** is the sweet spot. Pure synthetic underperforms the mix. https://arxiv.org/abs/2510.01631

**Lesson:** "high-IQ" in this field operationally means **synthetic textbooks generated by a frontier teacher, mixed 1:2 with filtered natural web data**. Pure curation of existing books is *not* what produced the gains. This contradicts the strict form of the thesis.

---

## §6. The picture this paints

A 14B model on heavily curated + synthetic data beats GPT-4o on graduate-level reasoning. A 1.5B distilled from R1 beats GPT-4o on AIME. A 7B math specialist beats Llama-3.1-405B. **None of these are exotic claims; they are the median outcome of three independent recipes (Phi, DeepSeek, Qwen) plus replications by NVIDIA (AceMath), Microsoft Research Asia (rStar-Math), and Skywork.**

The frontier of the user's idea — small + curated + reasoning — has been pursued at industrial scale. **TemLLM's job is not to discover the recipe.** It is to find an angle that has not been thoroughly explored: a specific domain, a specific curation choice, a specific evaluation, a specific deployment surface. See `OPEN_QUESTIONS.md`.
