# OPEN QUESTIONS — Decide Before Spending Compute

These are the load-bearing decisions. Each one changes the project meaningfully. Answers go in this file, dated and initialled.

---

## Q1 — What axis of "smart" are we optimizing for?

The strict thesis ("a 4B beats an 80B in intelligence") is unprovable as stated because "intelligence" isn't measured. We have to pick.

Candidates:
- **Math reasoning** (MATH, AIME, GSM8K, MathArena). Most crowded, strongest baselines (DeepSeek-R1-Distill-1.5B already beats GPT-4o here).
- **Formal theorem proving** (Lean, Coq; miniF2F, ProofNet). Less crowded, deeper moat, narrower utility.
- **Scientific reasoning** (GPQA Diamond, SciQ, ScienceQA). Intermediate.
- **Code review / static analysis** (no canonical benchmark — opportunity).
- **Long-form analytical writing** (LegalBench, SciBench, hard to evaluate).
- **Philosophical/ethical reasoning** (no good benchmark — interesting but evaluation is hard).
- **Tem-specific domain** — does this connect to the broader Tem / TEMM1E project? Should it?

**Decision:** _[pending]_

---

## Q2 — Build something new, or beat an existing baseline?

- **(a) Beat an existing baseline** at a specific task. Clear win condition; competitive landscape is brutal.
- **(b) Build a new evaluation surface** (e.g., a benchmark for a domain that doesn't have one) and ship a model that's strong on it. Lower competition, but you have to defend the benchmark.
- **(c) Build a tool / wrapper** (e.g., a CLI that fronts a small reasoning model with curated context) — product, not research.

**Decision:** _[pending]_

---

## Q3 — What does "high-IQ corpus" actually mean in this project?

Stating "math, science, philosophy, top 1% literature" is a starting intuition, not a corpus spec. We need:
- Concrete sources.
- A filter / scorer.
- A target token count.
- A mixture ratio (synthetic vs natural; per-domain weights).

The EMNLP 2025 result suggests **~33% synthetic + 67% filtered web** as a sweet spot. Override only with reason.

**Decision:** _[pending]_

---

## Q4 — Distillation source?

- **DeepSeek-R1 (open weights):** free to run, expensive in own compute, full reasoning traces available.
- **Qwen3-235B-Thinking / QwQ-32B (open):** cheaper to host, weaker than R1.
- **GPT-4o / o1 / o3 / Claude (API):** strongest, costs $$$, terms of service may forbid training competing models — **must check before generating any data**.
- **No distillation** — pure data curation. Slower path, but tests the strict thesis directly.

**Decision:** _[pending] — note: ToS of API providers must be reviewed if using closed models as teachers._

---

## Q5 — Base model or from scratch?

Per `FEASIBILITY.md`:
- **Continued pretrain on Qwen2.5-Base:** $2K–$15K, 1–4 weeks. Recommended.
- **From scratch:** $300K–$1M+. Not recommended at v0.
- **From scratch on tiny scale (10–100M params, nanoGPT-style)** as pedagogy: $0–$100. Useful for learning, not for results.

**Decision:** _[pending]_

---

## Q6 — How do we know the model is actually smart, not just benchmark-fit?

Phi's history is the warning. We need:
- **Held-out evaluation** the model has not seen — a private set written or commissioned for this project.
- **Format-perturbation tests** (Susan Zhang style) — same problem, different surface form.
- **Cross-benchmark consistency check** — does the model improve on benchmarks the corpus did *not* target?
- **Vibe testing** — actual humans using the model on their own problems. Not optional.

**Decision:** _[pending] — the eval must exist before any training run starts._

---

## Q7 — Single builder, or pull in collaborators?

This is the most frequently underestimated question. Pretraining is a team sport. Even Path B (continued pretrain) benefits from a second pair of eyes on the data pipeline because data bugs are expensive and silent.

**Decision:** _[pending]_

---

## Q8 — Compute budget commitment?

State a number. No number = no project.

- **$0–500:** Path A only (LoRA tinkering).
- **$500–5,000:** Path C (distillation) is in reach.
- **$5,000–50,000:** Path B (continued pretrain) is in reach.
- **$50,000+:** Path D (from scratch small) is in reach.

**Decision:** _[pending]_

---

## Q9 — Open or closed?

- Apache-2.0 / MIT release of weights, data recipe, training code? Or private?
- License of the *corpus* matters more than people expect — many curated sources are CC-BY-NC, which restricts commercial use of derived models.

**Decision:** _[pending]_

---

## Q10 — What is "done"?

Without an exit criterion, this becomes infinite. Options:
- A specific benchmark score (e.g. "TemLLM-7B beats DeepSeek-R1-Distill-7B on MathArena by ≥3 points").
- A specific deployment ("TemLLM CLI tool ships, used by N people").
- A specific report ("a paper or blog post answering: does narrow curation produce general-reasoning gains?").

**Decision:** _[pending]_

---

## Notes

- The decisions above must be made **in order**. Q1 changes everything downstream.
- Once Q1–Q4 are answered, `FEASIBILITY.md` should be re-read, the chosen path implemented, and a TRAINING_PLAN.md added.
- Until Q1 is answered, this is a research project, not a build project. **Do not write training code yet.**
