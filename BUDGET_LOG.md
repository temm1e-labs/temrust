# BUDGET LOG — Tem-Rust-1.7B

Hard cap: **$500**. Every cloud-GPU transaction logged here.

| date | phase | description | hours | rate | cost | running total |
|---|---|---|---|---|---|---|
| 2026-05-05 | pre-0 | Project planning, no compute | 0 | $0.00 | $0.00 | **$0.00** |

## Authorisations

| date | by | amount | scope |
|---|---|---|---|
| (pending) | Quan Duong | $500 | Tem-Rust v1 full pipeline |

## Spend rules (enforced)

1. Every cloud instance launch logged within same session
2. Single transaction > $50 requires explicit user confirmation
3. Running total > $400 triggers re-plan checkpoint
4. All Lambda instances must have `shutdown -h now` in startup script
5. Idle GPU > 30 min triggers automatic shutdown
