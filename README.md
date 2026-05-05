# TemLLM

**Goal:** ship the **best open ≤2B coding agent**, on a **$500 solo budget**.

Concretely: a **1.7B dense** post-trained model (Qwen3-1.7B-Base) that **beats Qwen2.5-Coder-3B-Instruct on SWE-bench Lite**, generalises on a **private post-cutoff GitHub-issue holdout**, and runs at **≥20 tok/s on M3 Pro at int4**. Stretch: 0.6B distillation; within 5 pts of Qwen3-Coder-Next on SWE-bench Verified.

The project went through two pivots on 2026-05-05:
1. **Pivot 1:** "general intelligence per param" → "agentic coding per param" (the original canon thesis is benchmark-fit, not utility — see `CHALLENGE.md`)
2. **Pivot 2:** 7B/$25–65K → **1.7B/$500/solo** (constraints from owner; the surprise-the-market angle is stronger at 1.7B than 7B)

**The original canon thesis survives as a 10–20% reasoning-data supplement in the SFT mix, ablated against pure-coding training.** That ablation is the testable novelty lever (see `PLAN.md` §3 and `OPEN_QUESTIONS.md` Q3).

---

## Read in this order

1. **[PLAN.md](./PLAN.md)** ← the locked project plan ($500/1.7B/solo). Start here.
2. **[PIPELINE.md](./PIPELINE.md)** — the 2026 SOTA toolchain (Unsloth + QLoRA + GRPO + hybrid verifier). Cite-able recipe.
3. **[OPEN_QUESTIONS.md](./OPEN_QUESTIONS.md)** — Q1–Q8 answered, Q9–Q10 still need decisions.
4. **[THEORY.md](./THEORY.md)** — the original thesis, captured verbatim.
5. **[CHALLENGE.md](./CHALLENGE.md)** — why the strict thesis was wrong, with citations.
6. **[PRIOR_ART.md](./PRIOR_ART.md)** — the small-curated-LLM landscape. Context, not directly applicable.
7. **[FEASIBILITY.md](./FEASIBILITY.md)** — generic small-model feasibility (superseded by `PLAN.md`).

When two docs disagree, `PLAN.md` wins.

---

## Status

- Phase: **Phase 0 — Foundations** (eval harness, baselines, build private holdout)
- Owner: Quan Duong (mini.illidan@gmail.com), solo
- Created: 2026-05-05
- Pivoted twice on 2026-05-05 (general → agentic-coding → $500/1.7B)
- No training code yet; eval first, baselines next.

## Win condition (one-line summary)

> A 1.7B open coding agent that beats Qwen2.5-Coder-3B-Instruct on SWE-bench Lite, generalises on a private post-cutoff holdout, runs on consumer hardware at int4 — fully reproducible at <$500 by a solo dev. Open weights, open recipe.
