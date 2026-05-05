# STATUS

**Last updated:** 2026-05-05 evening by Claude Code

## Current state

**Phase:** **Phase 0 — IN PROGRESS** (started 2026-05-05)
**Plan version:** v2 zero-risk, $75 actual funding ($50 RunPod + $25 Together)

**Authorisation:** "just do it im lazy" — user authorised $75 total spend, 2026-05-05.

## Setup completed
- [x] All 4 credentials saved to ~/.config/temllm/ (chmod 600)
- [x] All 4 API keys verified working (HF/GH/Together/RunPod)
- [x] Repo pushed to https://github.com/temm1e-labs/temrust (private, main, 6 commits)
- [x] Python venv created at .venv/ with `requests` + `huggingface_hub`
- [x] Project scaffold: scripts/, eval/, data/, configs/, outputs/
- [x] Helper scripts: load_creds.sh, runpod_check.py, together_check.py, together_serverless.py
- [x] Verified RunPod catalog: **RTX 4090 spot at $0.20/hr** is the cheapest reliable option for 1.7B QLoRA — 3× cheaper than A100 PCIe 80GB at $0.60/hr.
- [x] Verified Together AI serverless reality: only some catalog entries are actually serverless. **Qwen3-Coder-Next-FP8 IS serverless** ($0.50 in / $1.20 out per Mtok) — teacher pipeline confirmed.
- [x] **END-TO-END EVAL HARNESS WORKS** (2026-05-05). 3/3 hand-curated tasks pass on Qwen3-Coder-Next-FP8 via Together API.

## Verified serverless on Together (live tested)
- ✅ `Qwen/Qwen3-Coder-Next-FP8` ($0.50 in / $1.20 out per Mtok) — **planned teacher**
- ✅ `deepseek-ai/DeepSeek-V3.1` ($0.60 / $1.70 per Mtok) — teacher backup, strong baseline
- ❌ Qwen2.5-Coder-* / Llama-3.1-Turbo / DSR1-Distill-1.5B — **non-serverless** (require dedicated endpoints)

## Implication for Phase 0 baselines
Bases like Qwen3-1.7B-Base and Qwen2.5-Coder-1.5B are **non-serverless** on Together — must run locally on Mac via llama.cpp/Ollama OR rent a RunPod GPU. Plan: download GGUFs to Mac, baseline locally for free.

## Cost optimisation discovered
- Default training GPU: **RTX 4090 spot ($0.20/hr)** — was A100 40GB ($0.60/hr). 3× cheaper.
- Bases run locally on Mac (free) via llama.cpp/Ollama for Phase 0 baselines.
- Teacher = Qwen3-Coder-Next-FP8 on Together AI ($0.50/$1.20 per Mtok) — confirmed serverless.
- Revised expected committed: **~$15** (was $35) at $75 funded budget.

## Spent so far
$0.005 / $75.00 funded (smoke-test eval on Qwen3-Coder-Next-FP8, 3 tasks, ~6K tokens)

## Progress

| Phase | Status | Started | Completed | Spend |
|---|---|---|---|---|
| Pre-0 (planning) | ✅ Done | 2026-05-05 | 2026-05-05 | $0 |
| 0 (foundations) | 🟡 In progress | 2026-05-05 | — | $0 |
| 1 (data) | ⏸ | — | — | — |
| 2 (SFT v0) | ⏸ | — | — | — |
| 3 (synthetic + SFT v1) | ⏸ | — | — | — |
| 4 (GRPO) | ⏸ SKIPPED (zero-risk) | — | — | — |
| 5 (ship) | ⏸ | — | — | — |

## Key decisions locked

- Product: **Tem-Rust-1.7B**, Rust coding agent
- Base: Qwen3-1.7B-Base (fallbacks: Qwen3.5-2B-Base, Qwen2.5-Coder-1.5B-Base — all baselined Phase 0)
- Budget: **$200 hard cap, ~$35 expected committed, $165 reserve**
- Time: ~6-8 weeks
- Distribution: HuggingFace + crates.io + r/rust
- Compute: RunPod A100 40GB Community ($0.60/hr)
- Teacher: Qwen3-Coder-Next via Together AI hosted ($0.40/Mtok)
- **Phase 4 GRPO: SKIPPED** for zero-risk

See `PLAN.md` for full plan.

## Open questions (only release-related remain)

- Final landing page domain (default: GitHub Pages)
- TEMM1E integration: separate model or same? (decision deferred to Phase 5)

## Next action (immediate)

1. Build TemRust-Issue eval task harness — schema, runner, scorer
2. Curate first 5 TemRust-Issue tasks manually (smoke-test the format)
3. Run baseline: Qwen3-1.7B-Instruct via Together AI free tier on those 5 tasks (cost: $0)
4. If end-to-end passes: scale up to 50 tasks per sub-eval, 5 sub-evals
5. Then run baselines on all 9 candidate models

## Next action when "Continue Tem-Rust" is invoked

1. Read `STATUS.md` (this file)
2. Read `BUDGET_LOG.md` to confirm current spend
3. Check git log for last completed work
4. Resume the next pending task from the current phase
