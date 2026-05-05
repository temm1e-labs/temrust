# TemLLM

**Goal:** ship the **best open coding agent at its parameter size**.

Concretely: a 7B dense post-trained model that matches **DeepSWE-Preview-32B on SWE-bench Verified**, places **top-3 open at ≤7B on SWE-bench Pro**, and generalises on a **private post-cutoff GitHub-issue holdout**. Stretch: a 4B distillation that retains ≥80% of the 7B's score and runs on-device.

The project pivoted on 2026-05-05 from the original "small model trained on high-IQ canon" thesis after research found:
- The strict thesis (4B beats 80B in general intelligence) is **benchmark-fit, not utility** — see `CHALLENGE.md`
- "Best agent for its size" is a **specific, measurable, defensible** target — see `PLAN.md`
- The proven recipe (R2E-Gym + GRPO + verifier-driven distillation) is **achievable on a $25–65K budget over 6 months**

---

## Read in this order

1. **[PLAN.md](./PLAN.md)** ← the locked project plan. Start here.
2. **[OPEN_QUESTIONS.md](./OPEN_QUESTIONS.md)** — Q1–Q5 answered, Q6–Q10 still need decisions.
3. **[THEORY.md](./THEORY.md)** — the original thesis, captured verbatim, then unpacked.
4. **[CHALLENGE.md](./CHALLENGE.md)** — why the strict thesis was wrong, with citations.
5. **[PRIOR_ART.md](./PRIOR_ART.md)** — the small-curated-LLM landscape (Phi, DeepSeek-Math, Qwen-Math, rStar-Math). Context, not directly applicable to the new direction.
6. **[FEASIBILITY.md](./FEASIBILITY.md)** — generic small-model feasibility. The agent-specific paths in `PLAN.md` supersede this for the current project.

When two docs disagree, `PLAN.md` wins.

---

## Status

- Phase: **Phase 0 — Foundations** (eval harness, baselines, GPU procurement)
- Owner: Quan Duong (mini.illidan@gmail.com)
- Created: 2026-05-05
- Pivoted to agentic-coding focus: 2026-05-05
- No training code yet; eval first, baselines next.

## Win condition (one-line summary)

> A 7B dense open model that resolves real GitHub issues at 32B-class quality on a private, contamination-resistant holdout — published with weights, recipe, and technical report.
