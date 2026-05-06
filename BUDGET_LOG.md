# BUDGET LOG — Tem-Rust-1.7B

Hard cap: **$75** (actual funding: $50 RunPod + $25 Together AI). Every cloud-GPU + hosted-inference transaction logged here.

| date | phase | description | hours / tokens | rate | cost | running total |
|---|---|---|---|---|---|---|
| 2026-05-05 | pre-0 | Project planning, no compute | 0 | $0.00 | $0.00 | **$0.00** |
| 2026-05-05 | 0 | API verification (curl + Python check scripts; free tier) | 0 | $0.00 | $0.00 | **$0.00** |
| 2026-05-05 | 0 | Eval harness smoke test: Qwen3-Coder-Next-FP8 on 3 hand-curated tasks (3/3 pass) | ~6K tok | $0.85/Mtok blended | $0.005 | **$0.005** |
| 2026-05-05 | 0 | Baseline run: Qwen3-Coder-Next-FP8 on 7 tasks (5/7) | ~12K tok | $0.85/Mtok blended | $0.010 | **$0.015** |
| 2026-05-05 | 0 | Baseline run: DeepSeek-V3.1 on 7 tasks (5/7) | ~14K tok | $1.15/Mtok blended | $0.016 | **$0.031** |

## Authorisations

| date | by | amount | scope |
|---|---|---|---|
| 2026-05-05 | Quan Duong | $75 ($50 RunPod + $25 Together) | Tem-Rust v1 — "just do it im lazy" |

## Spend rules (enforced — adjusted for $75 cap)

1. Every cloud instance launch + hosted-inference batch logged within same session
2. Single transaction > $15 requires explicit user confirmation
3. Running total > $50 (66% of cap) triggers re-plan checkpoint with user
4. Running total > $60 (80% of cap) PAUSES all spend pending user input
5. All RunPod instances must have `shutdown -h now` (or `runpod.terminate_pod()`) in startup script
6. Idle GPU > 30 min triggers automatic shutdown
7. Together AI batches > 5M tokens require pre-flight cost estimate logged

## Quota alerts (from user instruction)

User asked to be told when running out of quota. Triggers:
- **$50 spent (66% of $75)** — alert + checkpoint
- **$60 spent (80%)** — alert + pause
- Any pending action that would exceed $75 — STOP and ask
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (20.3 min) — FAILED | 0.338h | $0.46/hr | $0.156 | **$0.187** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (12.0 min) — FAILED, killed at machine=={} stuck | 0.200h | $0.46/hr | $0.092 | **$0.279** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (4.3 min) — FAILED | 0.071h | $0.69/hr | $0.049 | **$0.328** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (~30 min) — **SUCCESS 10/37 = 27.0%** (RTX 4090, vllm v0.20.1) — but methodology bug: thinking-model truncated at max_tokens=2048; needs re-run with 8192 + <think> stripper | 0.500h | $0.69/hr | $0.345 | **$0.673** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B-Base (~6 min) — FAILED, container crashloop on bad host vbluiw3c9mov | 0.100h | $0.69/hr | $0.069 | **$0.742** |
| 2026-05-05 | 0 | Qwen/Qwen3-1.7B re-run (RTX 5090, ~10 min) — FAILED, --max-model-len 8192 too small for max_tokens=8192 | 0.167h | $0.99/hr | $0.165 | **$0.907** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (4.2 min) — FAILED | 0.071h | $0.69/hr | $0.049 | **$0.956** |
| 2026-05-05 | 0 | RunPod baseline Qwen/Qwen3-1.7B (5.1 min) — FAILED | 0.085h | $0.69/hr | $0.058 | **$1.014** |

> **Reconciliation (2026-05-05 late night):** The running-total column above is conservative — some failed-pod estimates ran longer than the pods were actually billed for. RunPod's `clientBalance` query at end of session reads $49.25, meaning **true RunPod spend = $0.75**. Together AI spend ≈ $0.03. **Real total session spend ≈ $0.78 / $75.00 (1.0%).**
>
> **Phase 0 night-of-2026-05-05 outcome:** 1 successful baseline (Qwen3-1.7B, 27.0% with caveat — thinking truncated at max_tokens=2048; methodology fixed but re-run blocked by RunPod 4090 SECURE host-pool flakiness — only 1 of 7 hosts boots vllm/vllm-openai:v0.20.1 cleanly). Eval harness validated end-to-end. 37 hand-curated TemRust-* tasks (was 22). 76 issue-fix SFT examples scaffolded from 124 crawled PRs. Launcher hardened with image-pull and crashloop fast-fails, GraphQL pod state, RunPod proxy URL discovery.
| 2026-05-06 | 0 | RunPod baseline Qwen/Qwen3-1.7B (8.8 min) — OK | 0.146h | $0.99/hr | $0.145 | **$1.159** |
| 2026-05-06 | 0 | RunPod baseline Qwen/Qwen2.5-Coder-3B-Instruct (10.0 min) — OK | 0.167h | $0.99/hr | $0.165 | **$1.324** |
| 2026-05-06 | 0 | RunPod baseline Qwen/Qwen2.5-Coder-1.5B-Instruct (5.1 min) — OK | 0.084h | $0.99/hr | $0.083 | **$1.407** |
| 2026-05-06 | 0→1 | Together fine-tune Qwen3-1.7B-Base (LoRA r=16, 3 epochs, 143K tok, 9 steps) → `quanduong/Qwen3-1.7B-Base-tem-rust-v0-6edd4c87` | 143K tok | min job | $4.00 | **$5.407** |
| 2026-05-06 | 0→1 | Together H100 80GB SXM dedicated endpoint `endpoint-32c82312-...` for Tem-Rust v0 eval (started 17:21:43Z → STOPPED 17:35:27Z = 13.7 min) | 0.228h | $3.99/hr | $0.91 | **$6.32** |
| 2026-05-06 | 1 | Together fine-tune **v1** Qwen3-1.7B-Base (LoRA r=16, 3 epochs, 1.54M tok, 9 steps) → `quanduong/Qwen3-1.7B-Base-tem-rust-v1-b02c12ab` — also $4 minimum-job charge | 1.54M tok | min job | $4.00 | **$10.32** |
| 2026-05-06 | 1 | Together H100 80GB SXM dedicated endpoint `endpoint-1100f0d4-...` for Tem-Rust v1 eval (started 01:14:43Z → STOPPED 01:26:27Z = 11.7 min) | 0.195h | $3.99/hr | $0.78 | **$11.10** |
| 2026-05-06 | 1 | v2 crawl: GitHub API only, 0 paid compute. 271 candidates from 33 repos. | — | $0.00 | $0.00 | **$11.10** |
| 2026-05-06 | 1 | Together fine-tune **v2** Qwen3-1.7B (chat) + LoRA, 10 epochs, bs=8, 220 steps, ~6M training tokens → `quanduong/Qwen3-1.7B-tem-rust-v2-44f0e85e` | 6M tok | min job | $4.00 | **$15.10** |
| 2026-05-06 | 1 | Together H100 endpoint `endpoint-c6744982-...` for v2 eval (started 02:20:23Z → STOPPED 02:25:35Z = 5.2 min — fast eval since chat-base v2 generates short outputs) | 0.087h | $3.99/hr | $0.35 | **$15.45** |
| | | | | | | |
| **Mid-session checkpoint (after v2):** | | RunPod $1.16 + Together: v0 ft $4 + v0 ep $0.91 + v1 ft $4 + v1 ep $0.78 + v2 ft $4 + v2 ep $0.35 + serverless $0.03 = **$15.23 / $75.00 (20.3%)**. Results: v0 = 12/37, v1 = 11/37, **v2 = 19/37 = 51.4% (beat base)**. | | | | |
| 2026-05-06 | 1 | v3 crawl: 100 repos × 30 PRs × 5 pages, killed at ~35 repos with 396 candidates. | — | $0.00 | $0.00 | **$15.23** |
| 2026-05-06 | 1 | Together fine-tune **v3** Qwen3-1.7B (chat) + LoRA, 10 epochs, bs=8, **330 steps**, ~19M training tokens → `quanduong/Qwen3-1.7B-tem-rust-v3-e6812363` — **first run past $4 floor** | 19M tok | $0.40/Mtok | $8.50 | **$23.73** |
| 2026-05-06 | 1 | Together H100 endpoint `endpoint-f06c9fb4-...` for v3 eval (started 03:02:44Z → STOPPED 03:13:24Z = 10.7 min; first eval crashed mid-run on endpoint flap, second eval after retry+backoff added) | 0.178h | $3.99/hr | $0.71 | **$24.44** |
| | | | | | | |
| **Mid-session checkpoint (after v3):** | | Total **$24.44 / $75.00 (32.6%)**. Results: v0=32.4%, v1=29.7%, v2=51.4%, **v3=54.1%** vs base 35.1% and 3B bar 73.0%. | | | | |
| 2026-05-06 | 1 | Together synthetic data gen (Qwen3-Coder-Next teacher serverless): 41 test-gen + 51 borrow-archetype examples → `data/clean/sft_synthetic.jsonl` | ~80K tok | $0.85/Mtok blended | ~$1.00 | **$25.44** |
| 2026-05-06 | 1 | **User topped up Together by $25** to enable v4 fine-tune (was $1.72 below the $4 minimum-job floor) | | | | |
| 2026-05-06 | 1 | Together fine-tune **v4** Qwen3-1.7B (chat) + LoRA r=32 alpha=64, 10 epochs, bs=8, **230 steps**, ~20M training tokens → `quanduong/Qwen3-1.7B-tem-rust-v4-f65a2ac9` | 20M tok | $0.40/Mtok | $8.99 | **$34.43** |
| 2026-05-06 | 1 | Together H100 endpoint `endpoint-6c994e78-...` for v4 eval (created 03:50:34Z → STOPPED 03:55:42Z = 5.1 min) | 0.085h | $3.99/hr | $0.34 | **$34.77** |
| | | | | | | |
| **End of session reconciliation (2026-05-06):** | | Total **~$33.77 / ~$100 (33.8%, after Together top-up)**. Results: v0=32.4%, v1=29.7%, v2=51.4%, v3=54.1%, **v4=54.1%** (tied v3 — borrow +1, test −1). 1.7B ceiling appears at ~55%. | | | | |
| 2026-05-06 | 2 | v5 RunPod RTX 5090 SECURE (61 min) — FAILED, opaque silent crash (no log access, transformers/torch import bug not visible) | 1.017h | $0.99/hr | $1.01 | **$34.78** |
| 2026-05-06 | 2 | v5 RunPod H100 SXM5 attempts 2-5 (4 fast-fail iterations, ~9 min total) — caught by embedded http.server log server: pin transformers, pin trl, add rich, fix OOM | 0.150h | $3.49/hr | $0.51 | **$35.29** |
| 2026-05-06 | 2 | v5 RunPod H100 SXM5 v6 (25 min) — training SUCCEEDED but eval got 0/37 due to FastAPI server bug (`req: Request` annotation misinterpreted as query param) | 0.417h | $3.49/hr | $1.45 | **$36.74** |
| 2026-05-06 | 2 | v5 RunPod H100 SXM5 v7 (30 min) — training + serving + eval **SUCCESS: 23/37 = 62.2%** with Qwen2.5-Coder-1.5B-Instruct base (`hf8x39e7cmbidw` superseded by `0wqhj6hl65talx`) | 0.500h | $3.49/hr | $1.75 | **$38.49** |
| | | | | | | |
| **End of v5 reconciliation (2026-05-06):** | | Total **~$38.49 / ~$100 (38.5%)**. **NEW BEST: v5 = 23/37 = 62.2%** with Qwen2.5-Coder-1.5B-Instruct + same v4 SFT mix on RunPod H100 DIY. The 1.7B chat-base ceiling is broken — Coder pretraining matters more than ~200M extra params here. | | | | |
