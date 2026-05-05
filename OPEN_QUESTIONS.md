# OPEN QUESTIONS

Almost all questions are now answered. Only one remains: **go / no-go**. See `PLAN.md` for the locked plan.

---

## ANSWERED

| Q | Answer | Locked |
|---|---|---|
| Q1 — axis of "smart"? | Best Rust coding agent at 1.7B | 2026-05-05 |
| Q2 — build new or beat existing? | Beat existing on Rust-specific eval | 2026-05-05 |
| Q3 — corpus? | `cargo`-verified Rust trajectories (issues, compile errors, test pairs, clippy) | 2026-05-05 |
| Q4 — teacher? | Qwen3-Coder-Next (primary) or DSR1-Distill-Qwen-14B (fallback). Open only. | 2026-05-05 |
| Q5 — base? | Qwen3-1.7B-Base (fallback Qwen2.5-Coder-1.5B-Base) | 2026-05-05 |
| Q6 — eval? | TemRust-* (Borrow, Type, Test, Clippy, Issue) — 250 tasks, hand-curated, `cargo`-verified | 2026-05-05 |
| Q7 — solo or collab? | Solo + Claude Code as autonomous executor | 2026-05-05 |
| Q8 — budget? | $500 hard cap, self-funded | 2026-05-05 |
| Q9 — open or closed? | Apache-2.0 weights + recipe + CLI; HuggingFace + crates.io | 2026-05-05 |
| Q10 — done criterion? | §0 win condition met → public release on HF + crates.io + r/rust launch post | 2026-05-05 |

---

## REMAINING

### Q11 — Go / no-go?

User must:
1. Set up credentials (Lambda + HF + GitHub) per `AUTOMATION.md` §1
2. Authorise the $500 budget in writing in-session
3. Say "Go" — Phase 0 starts immediately

**Status: pending.**

### Q12 — Connection to TEMM1E?

Deferred to Phase 5. Two ship options:
- (a) Tem-Rust-1.7B as the brain inside TEMM1E's Rust runtime — natural fit
- (b) Tem-Rust-1.7B as a fully independent product, TEMM1E uses it OR uses frontier APIs

**Decide at Phase 5 based on TEMM1E's state at that point.**

### Q13 — Landing page domain?

Default: GitHub Pages at `tem-llm.github.io`. User can override with custom domain (`tem-rust.dev` etc.) at Phase 5.

**Decide at Phase 5.**
