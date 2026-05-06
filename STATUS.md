# STATUS

**Last updated:** 2026-05-06 afternoon by Claude Code (continuation session — v5 Coder base swap)

## Current state

**Phase:** **Phase 1 (training pipeline) — v5 SHIPPED at 62.2%, new best. RunPod DIY pipeline locked.**
**Plan version:** v2 zero-risk, $75 actual funding ($50 RunPod + $25 Together)

**Authorisation:** "just do it im lazy" + "keep going until done" + "do until done i expect TemRust model ready by morning with full reports and benchmark" + "I think we should try finetuning qwen coder on runpod because it has a higher base" + "If fail investigate i want v5 use h100 to speed up if needed"

## Morning of 2026-05-06 outcome (v0–v4 on Qwen3-1.7B chat base)

- **v0 (diff SFT, 76 ex, 9 steps):** 12/37 = 32.4% — regression
- **v1 (whole-file SFT, 79 ex, 9 steps):** 11/37 = 29.7% — regression. Controlled experiment: format isn't the bottleneck.
- **v2 (chat base + whole-file SFT, 176 ex, 220 steps):** 19/37 = 51.4% — first to beat base.
- **v3 (chat base + whole-file SFT, 263 ex, 330 steps):** 20/37 = 54.1% — diminishing returns confirmed.
- **v4 (chat base + 263 PR + 41 synth-test + 51 synth-borrow, LoRA r=32, 230 steps):** 20/37 = 54.1% — tied v3 (borrow +1 from synthetic archetypes; test −1, synthetic teacher tests didn't transfer).
- All five Together dedicated endpoints confirmed STOPPED.

## Afternoon of 2026-05-06 outcome (v5 — base swap to Qwen2.5-Coder-1.5B-Instruct)

- **v5 (Qwen2.5-Coder-1.5B-Instruct + LoRA r=32, same v4 355-row SFT mix, 285 effective steps, RunPod H100 DIY):** **23/37 = 62.2% — NEW BEST.** Per-category: borrow 6/10 (+1 vs v4), issue 6/9 (−2), test 5/9 (+2), type 6/9 (+2). +3 tasks / +8.1 pp over v4 with 200M FEWER params.
- **The 1.7B chat-base "ceiling" is broken.** It was an artefact of the chat base's instruction-following bias on issue tasks — Coder pretraining transfers better to type/test/borrow at this size class.
- **RunPod DIY pipeline locked.** 7 attempts: v1 5090 silent (61 min, $1.01, killed), v2-v5 H100 fast-fail iterations (~$0.50 total), v6 H100 trained but FastAPI server bug (broke 0/37 eval, $1.45), v7 H100 fixed and shipped ($1.74). Total v5 spend ~$4.71. **Decisive engineering win**: embedded `python -m http.server :8001` log server in dockerStartCmd let us read `setup.log` over the public proxy — without it we'd have iterated blind.
- Pinned working stack: `transformers==4.45.2 peft==0.13.2 trl==0.11.4 accelerate==1.0.1 datasets==3.0.2 rich>=13 sentencepiece protobuf fastapi uvicorn` on `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`.
- Total session spend: **~$38.49 / ~$100.00 (38.5%, after Together top-up)**.

## Phase 0 progress (2026-05-05 → 2026-05-06)

- Eval harness validated end-to-end on Together (Qwen3-Coder-Next-FP8 88.9%, DeepSeek-V3.1 71.4%).
- **Qwen/Qwen3-1.7B (chat/thinking) baseline**: 10/37 = 27.0% with broken methodology (max_tokens=2048 truncated thinking) → **13/37 = 35.1% with methodology fix** (max_tokens=8192 + `<think>` stripper). Borrow recovered from 0/10 → 3/10.
- **Hand-curated tasks**: 22 → 37 (added 15 across borrow/type/test/issue).
- **Issue→SFT conversion**: 124 crawled candidates → 76 SFT examples scaffolded (61% yield, no cargo-verification yet — that's Phase 1).
- **RunPod launcher hardened**: REST + GraphQL hybrid, image-pull fast-fail, container-crashloop fast-fail, post-launch real-rate cost cap, proxy URL discovery, 16K context, 30GB containerDisk. See `feedback_runpod_diagnostics.md` in user memory.
- **Working host config**: RTX 5090 SECURE @ $0.99/hr boots cleanly (`24gxiv7zql7a`). RTX 4090 SECURE pool is flaky (1 of 7 hosts boots vllm v0.20.1).
- **Workload→provider rule LOCKED** (in AUTOMATION.md + user memory): Together AI for serverless-live large baselines, RunPod + vllm for everything else, Mac local ONLY for Phase 5 deployment validation.

## Baselines completed (TemRust-* n=37 tasks; chat models only)

| Model | Pass | Rate | Notes |
|---|---|---|---|
| Qwen/Qwen3-Coder-Next-FP8 | 14/22 (older n=22) | 88.9% pre-fix | Together AI serverless |
| deepseek-ai/DeepSeek-V3.1 | 5/7 (older n=7) | 71.4% | Together AI serverless |
| Qwen/Qwen3-1.7B (broken methodology) | 10/37 | 27.0% | thinking truncated |
| Qwen/Qwen3-1.7B (FIXED methodology) | 13/37 | 35.1% | RTX 5090, 16K ctx, max_tokens 8192 |
| Qwen/Qwen2.5-Coder-1.5B-Instruct | 19/37 | 51.4% | RTX 5090 — **v5 base** |
| Qwen/Qwen2.5-Coder-3B-Instruct | 27/37 | 73.0% | RTX 5090 — next bar to beat |

## Tem-Rust models trained (TemRust-* n=37)

| Version | Base | Pass | Rate | Provider | Notes |
|---|---|---|---|---|---|
| v0 | Qwen3-1.7B-Base | 12/37 | 32.4% | Together H100 | diff SFT, 9 steps |
| v1 | Qwen3-1.7B-Base | 11/37 | 29.7% | Together H100 | whole-file SFT, 9 steps |
| v2 | Qwen3-1.7B (chat) | 19/37 | 51.4% | Together H100 | first to beat base, 220 steps |
| v3 | Qwen3-1.7B (chat) | 20/37 | 54.1% | Together H100 | 263 ex, 330 steps |
| v4 | Qwen3-1.7B (chat) | 20/37 | 54.1% | Together H100 | 355 ex (v3 + 92 synthetic), r=32, 230 steps |
| **v5** | **Qwen2.5-Coder-1.5B-Instruct** | **23/37** | **62.2%** | **RunPod H100 DIY** | **BEST**, same 355 ex as v4, r=32, 285 steps |
| v5.1 | Qwen2.5-Coder-1.5B-Instruct | 22/37 | 59.5% | RunPod H100 DIY | regression: 397 ex (cleaned PR + broader synth), r=64, 15 epochs, lr=1e-5. Borrow regressed -2; type +1; net -1. NOT released |

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

## Spent so far (end of night)
**~$0.78 / $75.00 funded** (≈1.0% of budget; reconciled vs. RunPod's `clientBalance` query). See BUDGET_LOG.md for line-by-line.
- Together AI: ~$0.03 (smoke + 2 baseline runs)
- RunPod: $0.75 truth (per balance API). 7 launches: 1 success (Qwen3-1.7B, 27% with thinking-truncation caveat), 6 failures (5 host-pool stuck/crashloop, 1 max-model-len mismatch).

## Why night ended early
4 baselines re-attempted after the 27% Qwen3-1.7B result; all failed. Pattern: RunPod RTX 4090 SECURE pool has multiple hosts where vllm/vllm-openai:v0.20.1 starts but uptime stays 0 + ports stay null indefinitely (container crashlooping, no log access). Of 7 hosts allocated, only `et2ez1wnecks` booted cleanly. Fast-fail at 4-min crashloop deadline kept each failed attempt ≤$0.05. Total wasted on host-pool flakiness: ~$0.30.

## Methodology fix (READY but unused — needs successful pod to validate)
- `eval/extractors.py`: strip `<think>...</think>` (closed) and drop content from unclosed `<think>` (truncation).
- `eval/runner.py`: max_tokens 2048 → 8192. Catches Qwen3 thinking models that need reasoning headroom.
- `scripts/runpod_baseline.py` `dockerStartCmd`: `--max-model-len 16384` (was 8192) — leaves room for prompt + 8K thinking + answer in vllm context.
- Existing `Qwen__Qwen3-1.7B__1777996746.json` shows 15/27 failures were truncated thinking. Expected re-run pass rate: 16-19/37 = 43-51%.

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
