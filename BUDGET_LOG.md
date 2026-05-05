# BUDGET LOG — Tem-Rust-1.7B

Hard cap: **$200** (zero-risk plan). Every cloud-GPU + hosted-inference transaction logged here.

| date | phase | description | hours / tokens | rate | cost | running total |
|---|---|---|---|---|---|---|
| 2026-05-05 | pre-0 | Project planning, no compute | 0 | $0.00 | $0.00 | **$0.00** |

## Authorisations

| date | by | amount | scope |
|---|---|---|---|
| (pending) | Quan Duong | $200 | Tem-Rust v1 zero-risk full pipeline |

## Spend rules (enforced)

1. Every cloud instance launch + hosted-inference batch logged within same session
2. Single transaction > $30 requires explicit user confirmation
3. Running total > $150 triggers re-plan checkpoint
4. All RunPod instances must have `shutdown -h now` (or `runpod.terminate_pod()`) in startup script
5. Idle GPU > 30 min triggers automatic shutdown
6. Together AI batches > 1M tokens require pre-flight cost estimate logged
