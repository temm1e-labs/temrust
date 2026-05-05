# PLAN — Best Open ≤2B Coding Agent (Solo, $500)

**Locked 2026-05-05** after second pivot from 7B/$25-65K to **1.7B/$500/solo**. This document is authoritative. When earlier docs disagree, this wins.

---

## §0. Win Condition (recalibrated)

A **1.7B dense post-trained model** that, by end of project, satisfies **all** of:

1. **Primary — Beat Qwen2.5-Coder-3B-Instruct on SWE-bench Lite** at 1.7B params. The "1.7B beats 3B" surprise moment.
2. **SWE-bench Verified ≥ 20%** — credible for the size class (no public 1B-2B model has cleared this without distillation tricks).
3. **Private holdout (30–50 post-cutoff GitHub issues) ≥ 25%** — proves we generalise beyond contamination.
4. **Inference: ≥ 20 tok/s on M3 Pro at int4** — runnable on the user's actual laptop.
5. **Position: top open coding agent at ≤ 2B params** on at least one public leaderboard at release.

**Stretch (if budget allows after primary hit):**
- Within 5 points of Qwen3-Coder-Next (3B-active MoE) on SWE-bench Verified
- 0.6B distillation that retains ≥ 70% of 1.7B score (mobile / iPhone class)

**Out of scope:** general chat, world knowledge, vision, voice, multilingual writing. We do **one thing**: resolve real GitHub issues at 1.7B.

---

## §1. Constraints

| Constraint | Value |
|---|---|
| Param size (primary) | 1.7B dense (Qwen3-1.7B-Base) |
| Param size (stretch) | 0.6B (Qwen3-0.6B-Base) |
| Compute budget | **$500 hard cap** |
| Calendar time | ~3 months solo |
| Headcount | 1 (solo dev: Quan) |
| Base model | Qwen3-1.7B-Base (primary), Qwen2.5-Coder-1.5B-Base (fallback) |
| Teacher | DeepSeek-R1-Distill-Qwen-32B (free open) primary; DeepSeek-V3.1 API only if cheap; **no Claude/GPT-5** (ToS + cost) |
| License (output) | Apache-2.0 weights + recipe (assume permissive unless dataset licences forbid) |

---

## §2. Recipe (5 phases)

### Phase 0 — Foundations (FREE, 1–2 weeks)

Eval-first. No training until baselines and private holdout exist.

**Local Mac (M-series):**
- Install Unsloth (`pip install unsloth`), Axolotl backup, TRL, vllm
- Wire up SWE-bench Verified runner + SWE-bench Lite + private holdout runner
- Run baselines on rented cheap GPU OR free Kaggle/Colab T4:
  - Qwen3-1.7B-Base
  - Qwen3-1.7B-Instruct
  - Qwen2.5-Coder-1.5B-Instruct
  - DeepSeek-R1-Distill-Qwen-1.5B
  - Qwen2.5-Coder-3B-Instruct (the target to beat)

**Private holdout: build manually.**
- 30–50 fresh GitHub issues, opened **after** Qwen3 base cutoff (~Jan 2026)
- Active repos with passing CI
- Languages: Python (primary), TypeScript, Rust, Go (each 5–10)
- Each annotated with: issue text, repo state, expected behaviour, test command

**Exit criterion:** every benchmark runs reproducibly on at least one baseline. Private holdout exists. Choice of base model is locked.

**Cost: $0.** All free or trivial.

### Phase 1 — QLoRA SFT v0 (Weeks 3–5)

**Goal:** beat Qwen2.5-Coder-1.5B-Instruct on SWE-bench Lite using only public data.

Datasets:
| Source | Items | Role |
|---|---|---|
| **R2E-Gym** | 8.1K problems | Primary agent traces |
| AceCoder / AceCode-89K | 89K | SFT density |
| OpenHands trajectories | mixed | Tool-use diversity |
| **Reasoning supplement (10–20%)** | ~1K from MetaMathQA + OpenMathInstruct-2 + algorithms | The canon-thesis ablation |
| Tulu-3 (filtered for tool use) | ~1K | Format diversity |

Pipeline:
1. Pull, normalise to chat-format with tool calls
2. **Aggressive curation: filter to 500–5,000 highest-quality examples**. 2026 wisdom: 500 clean > 5,000 noisy.
3. **Decontamination: n-gram + embedding match against every eval set; drop overlap.**
4. SFT with Unsloth QLoRA on Qwen3-1.7B-Base
   - rank=16, alpha=32, dropout=0.05
   - LR 2e-4, cosine, 3 epochs, batch 4 grad-accum 8
   - Single A100 (Lambda spot ~$1.50/hr) for 12–24 hours
5. **Run two checkpoints**: with reasoning supplement vs without. **This is the ablation.**

**Exit criterion:** beat Qwen2.5-Coder-1.5B-Instruct on SWE-bench Lite by ≥ 3 pts AND show direction on private holdout.

**Cost: $20–50.**

### Phase 2 — Synthetic Distillation (Weeks 6–8)

**Goal:** add post-cutoff issue trajectories the open SFT corpus doesn't have.

Pipeline:
1. Curate ~500 real GitHub issues from post-base-cutoff dates in active repos (Python/TS/Rust/Go) with passing existing tests
2. Wrap each in an R2E-Gym-style executable env (use SWE-Playground recipe)
3. Run agent loop with **DeepSeek-R1-Distill-Qwen-32B** (open, free, run locally via Ollama or rented A100 inference) as teacher
4. Keep ONLY trajectories whose final patch passes all originally-passing tests AND breaks no other tests
5. Aim for 2,000–5,000 verified trajectories (cost gate)
6. SFT round 2 with QLoRA on union of (Phase 1 best mix + new synthetic)

**Why DeepSeek-R1-Distill-32B as teacher:** open weights, free if self-hosted, strong code+reasoning, no ToS risk. Inference cost = GPU rental, ~$1.50/hr × runtime.

**Exit criterion:** ≥ +5 points on SWE-bench Lite vs Phase 1 best.

**Cost: $100–200.** (Most goes to teacher inference + SFT compute.)

### Phase 3 — GRPO Mini-RL (Weeks 9–11)

**Goal:** push from "good imitation" to "actually solves problems" via verifiable reward.

Setup:
- Environment: **R2E-Gym 200–500 problems** (small slice — full 4,500 is out of budget)
- Algorithm: **GRPO with Unsloth** (works on free T4 / 16GB VRAM)
- Reward shaping:
  - Primary: all repo tests pass (sparse, ±1)
  - Shaping: code parses (+0.05), runs (+0.05), no regressions (+0.1), patch ≤ 200 LOC (penalty if over)
- Curriculum: easy → hard, ordered by Phase 2 teacher difficulty rating
- **Hard cap: $200 of compute. If not converging at 30% pass-rate by midpoint, stop and ship Phase 2 model.**

Exit criterion: SWE-bench Lite score ≥ Qwen2.5-Coder-3B-Instruct (the primary win condition).

**Cost: $100–200.**

### Phase 4 — Inference Scaling, Quantization, Ship (Weeks 12–14)

- Implement **R2E-Gym hybrid verifier** at inference: execution-based + execution-free, weighted, n=4 rollouts → best-of-n. Buys 5–10 points free.
- **int4 quantization** via llama.cpp / Unsloth / GGUF; verify ≥ 20 tok/s on M3 Pro
- Final eval pass: SWE-bench Verified, Lite, Live (sample), τ-bench, **private holdout**
- Decide:
  - Win condition met → public release: HuggingFace weights + Apache-2.0 + technical report + recipe gist
  - Not met → ship the technical report regardless. Negative results count.
- **Stretch: distill 1.7B → 0.6B** if any budget remaining.

**Cost: $0–50.**

---

## §3. Edges — Why This Could Actually Surprise

We will not outspend Alibaba. Our edges:

1. **Narrowness on a fresh size class.** Almost nobody has put serious post-training compute on 1.7B coding agents. The space is empty.
2. **The reasoning supplement ablation.** Most agent-coding fine-tunes are pure-coding. We mix 10–20% formal reasoning. If it transfers, that's a publishable result; if it doesn't, that itself is informative.
3. **Post-cutoff data.** Phase 2 synthetic uses issues none of the bases have seen.
4. **Hybrid-verifier inference.** Not all teams ship this; we make it standard.
5. **2026-vintage open teachers.** DeepSeek-R1-Distill-32B distilled into a 1.7B is a recipe that fits on consumer rentals.

What is **not** an edge: novel architecture, novel optimizer, novel scaling law, raw compute.

---

## §4. Tooling Stack (every step)

| Layer | Choice | Why |
|---|---|---|
| Base | Qwen3-1.7B-Base / Qwen2.5-Coder-1.5B-Base | Open, strong, Apache-2.0 |
| SFT framework | **Unsloth** | 2-5× faster, 80% less VRAM, free Colab/Kaggle support |
| QLoRA | Unsloth-native | rank=16, α=32 default |
| RL framework | **Unsloth GRPO** | Works on T4 16GB; fallback to TRL GRPO |
| Pipeline orchestration | **Axolotl** | YAML configs; Unsloth integration |
| Inference | **vllm** for batch eval; **llama.cpp/GGUF** for Mac | Standard |
| Quantization | llama.cpp int4/int2 GGUF | M-series Mac native |
| Eval | SWE-bench official harness | Standard |
| Tracking | Weights & Biases (free tier) | Standard |
| Compute | Lambda Labs spot A100 ($1.50/hr) + free Kaggle T4 | Cheapest reliable |
| Storage | Local NVMe + Cloudflare R2 (free tier) | Cheap egress |

---

## §5. Datasets

**Training (Phase 1–2):**
- R2E-Gym (https://github.com/R2E-Gym/R2E-Gym)
- AceCoder / AceCode-89K
- OpenHands trajectories
- MetaMathQA + OpenMathInstruct-2 (reasoning supplement)
- Tulu-3-SFT-Mixture (filtered)
- Phase 2 synthetic: ~2-5K verified trajectories (DSR1-Distill-32B teacher)

**Eval (decontaminated against training):**
- SWE-bench Verified (sampled 100 issues if full 500 is too expensive)
- SWE-bench Lite (300 issues, primary)
- SWE-bench-Live (rolling sample)
- τ-bench (tool use)
- **Private holdout (30–50 post-cutoff issues) — release-gate metric**

---

## §6. Budget Discipline

| Phase | Floor | Ceiling | Hard cap rule |
|---|---|---|---|
| 0 | $0 | $0 | Free only |
| 1 | $20 | $50 | Stop if no improvement vs base after 2 runs |
| 2 | $100 | $200 | Stop if synthetic data quality < 50% test-pass rate |
| 3 | $100 | $200 | Stop if not at 30% pass-rate by midpoint |
| 4 | $0 | $50 | One final eval run only |
| **Total** | **$220** | **$500** | One re-run's worth of margin |

**Spend rules:**
- Use **Lambda Labs spot A100** ($1.50/hr) as default rental
- Use **Kaggle / Colab T4** for free runs (smoke tests, eval, GRPO ablations)
- Never run >24 hrs without checking partial results
- Track every USD in `BUDGET_LOG.md` (to be created Phase 0)

---

## §7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 1.7B too small for tool-use reliability | High | Critical | Phase 0 baseline tells us early; if base fails 5% on Lite, drop to specialised TDD-only task or move to 3B |
| Eval contamination inflates scores | Very High | High | Private holdout is release-gate |
| GRPO doesn't converge at 1.7B | Med-High | Med | Fallback: ship Phase 2 model, drop GRPO |
| Synthetic data quality bad | Med | Med | Phase 2 quality gate: ≥ 50% trajectories pass tests, else re-tune teacher prompt |
| Single-builder data bug | High | Med | Daily distribution sanity-checks; commit datasets to git LFS |
| Frontier ships matching 1B coder before us | Low-Med | Med | Time-box 3 months; release SFT-only by Week 8 if needed |
| Budget overrun | Very High | High | Hard per-phase caps; weekly burn review |

---

## §8. Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-05-05 | Pivot from "general intelligence per param" to "agentic coding per param" | Strict canon thesis is benchmark-fit not utility |
| 2026-05-05 | Drop 7B/$25–65K plan; lock 1.7B/$500/solo | Solo dev with $500 max; surprise-the-market angle stronger at 1.7B |
| 2026-05-05 | Qwen3-1.7B-Base as primary (Qwen2.5-Coder-1.5B-Base fallback) | Strongest 1B-class base in 2026 |
| 2026-05-05 | Unsloth as SFT/RL framework | Single-GPU king; free Colab/Kaggle support; 80% VRAM reduction |
| 2026-05-05 | Open teachers only (DSR1-Distill-32B primary) | ToS + cost; can self-host |
| 2026-05-05 | Reasoning supplement (10–20%) is the originality lever, ablated | Salvages canon thesis as testable component |
| 2026-05-05 | Recalibrated win condition: beat Qwen2.5-Coder-3B-Instruct on SWE-bench Lite | Honest at 1.7B; "1.7B beats 3B" is the surprise |

Future decisions appended here, dated.

---

## §9. Next Action (this week)

1. Confirm win condition and constraints (user signs off / pushes back)
2. Install Unsloth on local Mac; verify it runs
3. Build private holdout: 30 fresh post-cutoff issues from active repos with green CI
4. Run baselines: Qwen3-1.7B-Base, Qwen3-1.7B-Instruct, Qwen2.5-Coder-1.5B-Instruct, Qwen2.5-Coder-3B-Instruct, DSR1-Distill-1.5B
5. Pick base model based on baseline + licence

After this is done, Phase 1 starts.
