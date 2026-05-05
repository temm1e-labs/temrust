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

## Phase 0 progress (2026-05-05 evening — milestone: harness validated)

| Item | Status | Notes |
|---|---|---|
| Eval schema + runner + verifier + extractor | ✅ | Working end-to-end |
| Hand-curated tasks | 🟡 7/200 (3 borrow, 2 type, 2 test) | Need 50 per sub-eval |
| Together-live baselines | ✅ 2 models (Qwen3-Coder-Next-FP8 71.4%, DeepSeek-V3.1 71.4%) | Both teachers competent on our task format |
| Non-serverless baselines (Qwen3-1.7B-Base, etc.) | ⏸ | Need local Mac inference (Ollama) — next session |
| Strand-Rust-Coder-14B baseline | ⏸ | Will run via local Ollama on Mac (M-series handles 14B at int4) |
| GitHub crawler (Phase 1 prep) | ⏸ | Scaffold next |
| RunPod training launcher | ⏸ | Scaffold next |

## Baseline scores (TemRust-* sub-eval, n=7 tasks total)

| Model | Borrow (3) | Type (2) | Test (2) | Total |
|---|---|---|---|---|
| Qwen3-Coder-Next-FP8 (teacher) | 3/3 | 2/2 | 0/2 | 5/7 (71.4%) |
| DeepSeek-V3.1 | 2/3 | 2/2 | 1/2 | 5/7 (71.4%) |

**Insight:** test-generation is hardest sub-eval (matches Strand paper finding "largest improvements in test generation"). Both top models fail there, leaves clear room for our specialist.

## Next action (next session)

1. **Set up local Mac inference for non-serverless bases.** Install Ollama: `brew install ollama && ollama serve`. Pull `qwen2.5-coder:1.5b`, `qwen3:1.7b`, `qwen3:0.6b`, `deepseek-r1:1.5b`. Add `eval/clients.py:OllamaClient`. Run baselines.

2. **Pull Strand-Rust-Coder-14B GGUF** from HF and run baseline locally via Ollama (will be slow on Mac but free).

3. **Curate more eval tasks.** Target ~10 per sub-eval (40 total) for richer baselines. Source ideas: Rust by Example, rustc UI tests, real GitHub issues.

4. **Begin Phase 1 GitHub crawler.** scripts/crawl_rust_issues.py — find merged PRs in popular Rust repos that close issues + add tests. Save metadata to data/raw/issues.jsonl.

5. **Begin RunPod launcher.** scripts/launch_train.py — provisions RTX 4090 spot, runs training via cloud-init script, auto-shuts. Smoke-test with 1-min trivial workload (~$0.005).

## Spent so far
**$0.02 / $75.00 funded** (≈0.03% of budget)
- API verification: $0
- Smoke test: $0.005
- Baselines on 2 models × 7 tasks: ~$0.015

## Next action when "Continue Tem-Rust" is invoked

1. Read `STATUS.md` (this file)
2. Read `BUDGET_LOG.md` to confirm current spend
3. Check git log for last completed work
4. Resume the next pending task from the current phase
