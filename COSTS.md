# COSTS — Exact Math, $500 Hard Cap

Every dollar accounted for. Updated as spend happens (see `BUDGET_LOG.md`).

---

## Reference Pricing (May 2026 spot)

| Resource | Provider | Price | Notes |
|---|---|---|---|
| 1× A100 80GB | Lambda Labs spot | **$1.49 / hr** | Default rental |
| 1× A100 80GB | RunPod Community | $1.19 / hr | Cheaper backup |
| 1× A100 80GB | vast.ai | $0.60–0.90 / hr | Cheapest, less reliable |
| 1× H100 80GB | Lambda Labs spot | $2.49 / hr | If needed for teacher |
| Kaggle T4 | Free | $0 | 30 hrs/week |
| Colab T4 | Free | $0 | Limited, no SLA |
| HuggingFace inference | Free tier | $0 | Rate-limited |
| GitHub API | Free tier | $0 | 5K req/hr |
| Storage (HF) | Free | $0 | Public repos |
| Storage (Cloudflare R2) | $0 / 10 GB | $0 | Free tier sufficient |
| W&B tracking | Free tier | $0 | Plenty for solo |

---

## Throughput Constants

**Qwen3-1.7B QLoRA on A100:**
- ~10K tokens/sec with sequence packing (Unsloth)
- ~3 hrs per training run on 5K examples × 4K avg ctx × 3 epochs

**DeepSeek-R1-Distill-Qwen-14B on A100 (vllm fp8):**
- ~50 tokens/sec output
- ~17 hrs to generate 3M output tokens

**Qwen3-Coder-Next (3B-active MoE) on A100 (vllm bf16):**
- ~80 tokens/sec output
- ~10 hrs to generate 3M output tokens (preferred teacher if accessible)

**Eval (1.7B model on 50 tasks via vllm):**
- ~30 sec/task × 50 tasks = 25 min wall time
- 250-task full suite: ~2 hrs per model

---

## Phase-by-Phase Math

### Phase 0 — Foundations ($20)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Cloud setup + smoke tests | 2 | $1.49 | $2.98 |
| Baseline eval runs (5 models × 250 tasks) | 5 | $1.49 | $7.45 |
| Buffer (re-runs, debugging) | — | — | $9.57 |
| **Phase 0 total** | | | **$20** |

### Phase 1 — Data Collection ($0)

All local CPU + GitHub free tier. Zero compute spend.
- Crawling: ~2 days wall time on local Mac
- Verification: parallel `cargo test` runs in Docker on local Mac
- Decontamination: local

### Phase 2 — SFT v0 ($30)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Hyperparameter sweep run 1 | 3 | $1.49 | $4.47 |
| Hyperparameter sweep run 2 | 3 | $1.49 | $4.47 |
| Hyperparameter sweep run 3 | 3 | $1.49 | $4.47 |
| Mid-eval run 1 | 2 | $1.49 | $2.98 |
| Mid-eval run 2 | 2 | $1.49 | $2.98 |
| Mid-eval final | 2 | $1.49 | $2.98 |
| Buffer (rerun if first config bad) | — | — | $7.65 |
| **Phase 2 total** | | | **$30** |

### Phase 3 — Synthetic + SFT v1 ($45)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Teacher inference (Qwen3-Coder-Next ~10 hrs OR DSR1-Distill-14B ~17 hrs) | 15 (avg) | $1.49 | $22.35 |
| SFT v1 training | 4 | $1.49 | $5.96 |
| Eval (full TemRust-* suite) | 2 | $1.49 | $2.98 |
| Buffer | — | — | $13.71 |
| **Phase 3 total** | | | **$45** |

### Phase 4 — GRPO Mini-RL ($50, optional)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| GRPO training (hard cap 24 hrs) | 24 | $1.49 | $35.76 |
| Eval | 2 | $1.49 | $2.98 |
| Buffer | — | — | $11.26 |
| **Phase 4 total** | | | **$50** |

**SKIP RULE:** if Phase 3 v1 hits the §0 win condition, skip Phase 4 and bank $50 to reserve.

### Phase 5 — Quantize, Package, Ship ($10)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Final eval suite run | 2 | $1.49 | $2.98 |
| Quantization (local) | — | — | $0 |
| CLI development (local) | — | — | $0 |
| Demo gif recording (local) | — | — | $0 |
| HF upload, crates.io publish, blog | — | — | $0 |
| Buffer | — | — | $7.02 |
| **Phase 5 total** | | | **$10** |

---

## Grand Total

| | Floor | Ceiling |
|---|---|---|
| Phase 0 | $20 | $20 |
| Phase 1 | $0 | $0 |
| Phase 2 | $30 | $30 |
| Phase 3 | $45 | $45 |
| Phase 4 (optional) | $0 (if skipped) | $50 |
| Phase 5 | $10 | $10 |
| **Committed (with Phase 4)** | **$105** | **$155** |
| **Reserve for unexpected** | **$345–395** | |
| **Hard cap** | | **$500** |

The reserve covers: re-runs after bugs, expanded synthetic data if needed, additional eval beyond the 250-task suite, infra mistakes (forgot to shut down a GPU, etc.), or expanding to a 0.6B distillation stretch goal.

---

## Spend Rules

1. **Every cloud transaction logged in `BUDGET_LOG.md`** within the same Claude Code turn
2. **Single transaction > $50** requires explicit user confirmation in-session
3. **Total spend > $400** triggers a re-plan checkpoint with user
4. **All Lambda instances must have auto-shutdown on training completion** (`shutdown -h now` in startup script)
5. **Idle GPU > 30 min = shutdown via Lambda CLI** (Claude Code monitors)
6. **No closed-API teachers (Claude/GPT-5)** without explicit approval — open teachers only at v0
7. **Free tiers exhausted before paid:** Kaggle T4 + Colab T4 + HF inference free for any task that fits

---

## Cost Reduction Levers (if budget tightens)

- **Skip Phase 4 entirely** → save $50
- **Use vast.ai instead of Lambda** → ~40% cheaper, less reliable
- **Use DSR1-Distill-Qwen-7B as teacher** → $10 vs $25 for synthetic gen
- **Smaller eval (100 tasks instead of 250)** → save ~$5 per eval run
- **Shorter sequence length (4K instead of 8K)** → ~30% faster training
- **Drop GGUF Q5_K_M quant** (only ship Q4_K_M + Q2_K) → save $0 but less artifact

---

## Cost Tracking File

`BUDGET_LOG.md` is the live ledger. Every cloud-GPU instance launch + every shutdown logs:

```
| date | phase | what | hours | rate | cost | running_total |
| 2026-05-12 | 0 | Lambda A100 spot — baseline run Qwen3-1.7B-Base | 1.2 | $1.49 | $1.79 | $1.79 |
```

Running total never exceeds $500 without user re-authorisation.
