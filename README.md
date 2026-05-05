# TemLLM

A research project to interrogate, challenge, and (if it survives) prototype a thesis:

> **Train a small LLM only on high-IQ material — math, science, philosophy, top-tier engineering and literature — and it will outreason a generalist 10–20× its size.**

This repo opens with **research before code**. The goal of v0 is to know the shape of the prior art, the strongest counter-arguments, and the realistic feasibility envelope before a single token of compute is spent.

---

## How to read this repo

Read in this order:

1. **[THEORY.md](./THEORY.md)** — the thesis as the originator stated it, captured faithfully.
2. **[PRIOR_ART.md](./PRIOR_ART.md)** — what has already been built and published in this direction. Phi series, DeepSeek-Math, Llemma, Minerva, rStar-Math, FineWeb-Edu, the lot.
3. **[CHALLENGE.md](./CHALLENGE.md)** — the strongest counter-evidence. Where the thesis breaks, with citations.
4. **[FEASIBILITY.md](./FEASIBILITY.md)** — concrete paths from "do nothing" to "pretrain from scratch", with costs.
5. **[OPEN_QUESTIONS.md](./OPEN_QUESTIONS.md)** — what we have to decide before any compute is spent.

---

## Current verdict (one paragraph)

The thesis is **partially validated and partially wrong**, and the difference matters. The "small + curated > large + raw" idea has been the explicit research program of Microsoft (Phi), DeepSeek, Alibaba (Qwen-Math), Microsoft Research Asia (rStar-Math), and EleutherAI (Llemma) for ~3 years. They have produced 3–14B models that beat 70B+ generalists on **verifiable-reasoning** benchmarks (math, code, formal proof). They have **not** produced 4B models that beat 80B generalists on open-ended utility — knowledge recall, agent tasks, conversation, long-context coding. Phi-4 (14B, Dec 2024) scores 84.8 MMLU and 80.4 MATH but only **3** on SimpleQA where Llama-3-70B scores ~20. The "smarter than 80B" slogan is real on a narrow axis and false on a wide one. This is the design problem TemLLM has to confront.

The next decision is **scope**: which axis of "smart" do we actually want?

---

## Status

- Phase: **research / scoping**. No training code, no models.
- Created: 2026-05-05.
- Owner: Quan Duong (mini.illidan@gmail.com).
