# STATUS

**Last updated:** 2026-05-05 by Claude Code

## Current state

**Phase:** Pre-Phase-0 — awaiting user authorisation to begin.

**Pending blocker:** user must complete one-time setup (see `AUTOMATION.md` §1):
- [ ] Lambda Labs account funded with $500 + API key
- [ ] HuggingFace write token
- [ ] GitHub personal access token
- [ ] (Optional) Weights & Biases API key
- [ ] Written budget authorisation in-session: "I authorise up to $500 for Tem-Rust v1"

Once these are in place, Phase 0 starts immediately.

## Progress

| Phase | Status | Started | Completed | Spend |
|---|---|---|---|---|
| Pre-0 (planning) | ✅ Done | 2026-05-05 | 2026-05-05 | $0 |
| 0 (foundations) | ⏸ Awaiting auth | — | — | — |
| 1 (data) | ⏸ | — | — | — |
| 2 (SFT v0) | ⏸ | — | — | — |
| 3 (synthetic + SFT v1) | ⏸ | — | — | — |
| 4 (GRPO, optional) | ⏸ | — | — | — |
| 5 (ship) | ⏸ | — | — | — |

## Key decisions locked

- Product: **Tem-Rust-1.7B**, Rust coding agent
- Base: Qwen3-1.7B-Base (fallback Qwen2.5-Coder-1.5B-Base)
- Budget: $500 hard cap
- Time: ~10 weeks
- Distribution: HuggingFace + crates.io + r/rust

See `PLAN.md` for full plan.

## Open questions (only release-related remain)

- Final landing page domain (default: GitHub Pages)
- TEMM1E integration: separate model or same? (decision deferred to Phase 5)

## Next action when "Continue Tem-Rust" is invoked

1. Read `STATUS.md` (this file)
2. Read `BUDGET_LOG.md` to confirm current spend
3. Check git log for last completed work
4. Resume the next pending task from the current phase
