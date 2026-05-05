# Tem-Rust-1.7B

A 1.7B parameter Rust coding specialist. Fine-tuned from Qwen3-1.7B-Base on `cargo`-verified Rust trajectories. Runs offline at int4 on M-series Macs. Free, private, fast.

**Status: pre-Phase-0. Awaiting build authorisation.** See `STATUS.md`.

---

## What it does

- `tem-rust fix <file>` — fix rustc compile errors and borrow-checker issues
- `tem-rust test <file::fn>` — generate `#[test]` blocks
- `tem-rust review <diff>` — clippy-style code review
- `tem-rust explain <error>` — explain rustc error messages
- `tem-rust chat` — interactive REPL

Runs at ≥ 30 tok/s on M3 Pro at int4 (Q4_K_M GGUF, ~1 GB).

---

## Why it exists

Frontier LLMs (Claude, GPT) are notably weaker on Rust than on Python. They get borrow-checker fixes wrong, hallucinate trait bounds, and produce non-idiomatic code. **There is no top open small Rust coding specialist.** Tem-Rust fills the niche.

The project is built on a **$200 zero-risk budget** by a solo dev with Claude Code as autonomous executor. Expected committed spend: ~$35. Reserve: ~$165 (82% margin). Total user time across the 6-8 week build: ≤ 60 minutes.

---

## How it's built

1. **Base** — Qwen3-1.7B-Base (Apache-2.0)
2. **Data** — 7-8K `cargo`-verified Rust trajectories (real GitHub issues + synthetic compile errors + test pairs + clippy fixes + self-distillation)
3. **Train** — QLoRA SFT via Unsloth → optional GRPO with `cargo test` reward
4. **Quantize** — int4 GGUF (Q4_K_M) for M-series Macs
5. **Ship** — HuggingFace weights + `cargo install tem-rust` CLI + 30s demo + r/rust launch

Full plan in [`PLAN.md`](./PLAN.md). Technical pipeline in [`PIPELINE.md`](./PIPELINE.md). Exact cost math in [`COSTS.md`](./COSTS.md). Autonomous execution model in [`AUTOMATION.md`](./AUTOMATION.md).

---

## Read in this order

1. **[PLAN.md](./PLAN.md)** ← the build plan
2. **[PIPELINE.md](./PIPELINE.md)** — technical execution
3. **[COSTS.md](./COSTS.md)** — exact cost math, $500 hard cap
4. **[AUTOMATION.md](./AUTOMATION.md)** — how Claude Code drives this autonomously
5. **[STATUS.md](./STATUS.md)** — current state, updated weekly
6. **[BUDGET_LOG.md](./BUDGET_LOG.md)** — live spend ledger
7. **[OPEN_QUESTIONS.md](./OPEN_QUESTIONS.md)** — almost all closed
8. **[THEORY.md](./THEORY.md)** — original "high-IQ canon" thesis (history)
9. **[CHALLENGE.md](./CHALLENGE.md)** — why the strict thesis was wrong (history)
10. **[PRIOR_ART.md](./PRIOR_ART.md)** — small-curated-LLM landscape (context)
11. **[FEASIBILITY.md](./FEASIBILITY.md)** — generic small-model feasibility (superseded)

---

## Win condition (one-line)

> A 1.7B Rust coding agent that beats Qwen2.5-Coder-1.5B-Instruct by ≥ 10 pts on every TemRust-* sub-eval and is within 5 pts of Qwen2.5-Coder-7B-Instruct on most — public on HuggingFace, installable via `cargo install tem-rust`, runnable offline on a laptop.

---

## Status & Owner

- **Owner:** Quan Duong (mini.illidan@gmail.com), hands-off
- **Executor:** Claude Code (autonomous)
- **Created:** 2026-05-05
- **Direction locked:** 2026-05-05 (after four pivots — see `PLAN.md` §8)
- **Phase:** Pre-Phase-0 — awaiting user authorisation
