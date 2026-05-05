# BUDGET LOG — Tem-Rust-1.7B

Hard cap: **$75** (actual funding: $50 RunPod + $25 Together AI). Every cloud-GPU + hosted-inference transaction logged here.

| date | phase | description | hours / tokens | rate | cost | running total |
|---|---|---|---|---|---|---|
| 2026-05-05 | pre-0 | Project planning, no compute | 0 | $0.00 | $0.00 | **$0.00** |
| 2026-05-05 | 0 | API verification (curl + Python check scripts; free tier) | 0 | $0.00 | $0.00 | **$0.00** |
| 2026-05-05 | 0 | Eval harness smoke test: Qwen3-Coder-Next-FP8 on 3 hand-curated tasks (3/3 pass) | ~6K tok | $0.85/Mtok blended | $0.005 | **$0.005** |

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
