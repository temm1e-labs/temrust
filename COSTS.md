# COSTS — Exact Math, $200 Hard Cap, Zero-Risk

Every dollar accounted for. Updated as spend happens (see `BUDGET_LOG.md`).

---

## Reference Pricing (May 2026 verified)

| Resource | Provider | Price | Notes |
|---|---|---|---|
| 1× A100 PCIe 40GB | **RunPod Community** | **$0.60 / hr** | **Default rental — cheapest reliable A100** |
| 1× A100 80GB | RunPod Community | $1.19 / hr | Backup if 40GB insufficient |
| 1× A100 80GB | vast.ai spot | $1.00–1.80 / hr | Cheapest 80GB if needed |
| 1× A100 80GB | Lambda Labs | $2.49 / hr | Premium; not used in zero-risk plan |
| 1× H100 80GB | RunPod spot | $1.49 / hr | Only if A100 insufficient |
| Kaggle T4 | Free | $0 | 30 hrs/week — eval and smoke tests |
| Colab T4 | Free | $0 | Limited, backup |
| Together AI Qwen3-Coder-Next | Hosted | $0.40 / 1M tokens | **Teacher inference** |
| DeepInfra Qwen3-Coder-Next | Hosted | $0.30 / 1M tokens | Teacher fallback |
| HuggingFace Inference | Free tier | $0 | Rate-limited |
| GitHub API | Free tier | $0 | 5K req/hr |
| HF storage (public repos) | Free | $0 | Weights + GGUF |
| Cloudflare R2 | Free 10GB | $0 | Dataset cache |
| W&B free tier | Free | $0 | Tracking |

---

## Throughput Constants

**Qwen3-1.7B QLoRA on A100 40GB (Unsloth + 4K seq):**
- ~12K tokens/sec with sequence packing
- ~2.5 hrs per training run on 5K examples × 3 epochs

**Teacher inference via Together AI (Qwen3-Coder-Next):**
- $0.40 / 1M output tokens
- 3M output tokens (3K trajectories × ~1K tokens each) = $1.20

**Eval (1.7B model on 200 tasks via vllm):**
- ~30 sec/task × 200 = 100 min wall time (~1.7 hrs per full suite)

---

## Phase-by-Phase Math

### Phase 0 — Foundations ($10)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| RunPod setup + smoke tests | 1 | $0.60 | $0.60 |
| Baseline eval (6 models × 200 tasks ÷ batched) | 6 | $0.60 | $3.60 |
| Buffer (re-runs, debugging) | — | — | $5.80 |
| **Phase 0 total** | | | **$10** |

Models baselined:
- Qwen3-1.7B-Base
- Qwen3-1.7B (Instruct)
- Qwen3.5-2B-Base (NEW: alternative base candidate)
- Qwen2.5-Coder-1.5B-Base
- Qwen2.5-Coder-1.5B-Instruct (target to beat)
- Qwen2.5-Coder-7B-Instruct (stretch target)

### Phase 1 — Data Collection ($0)

All local CPU + GitHub free tier. Zero compute spend.

### Phase 2 — SFT v0 ($10)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Hyperparameter sweep run 1 | 2.5 | $0.60 | $1.50 |
| Hyperparameter sweep run 2 | 2.5 | $0.60 | $1.50 |
| Mid-eval run 1 | 1.5 | $0.60 | $0.90 |
| Mid-eval run 2 | 1.5 | $0.60 | $0.90 |
| Buffer | — | — | $5.20 |
| **Phase 2 total** | | | **$10** |

### Phase 3 — Synthetic + SFT v1 ($10)

| Item | Hours / Tokens | Rate | Cost |
|---|---|---|---|
| Teacher inference (Qwen3-Coder-Next via Together AI, 3M tokens) | 3M tokens | $0.40/Mtok | $1.20 |
| SFT v1 training | 4 | $0.60 | $2.40 |
| Eval (full TemRust-* suite) | 1.7 | $0.60 | $1.00 |
| Buffer | — | — | $5.40 |
| **Phase 3 total** | | | **$10** |

### Phase 4 — SKIPPED ($0)

GRPO removed for zero-risk. Save $50 from prior plan.

### Phase 5 — Quantize, Package, Ship ($5)

| Item | Hours | Rate | Cost |
|---|---|---|---|
| Final eval suite run | 1.7 | $0.60 | $1.00 |
| Quantization (local Mac) | — | — | $0 |
| CLI development (local Mac) | — | — | $0 |
| Demo gif recording (local Mac) | — | — | $0 |
| HF upload, crates.io publish, blog (local Mac) | — | — | $0 |
| Buffer | — | — | $4.00 |
| **Phase 5 total** | | | **$5** |

---

## Grand Total

| | Floor | Ceiling |
|---|---|---|
| Phase 0 | $5 | $10 |
| Phase 1 | $0 | $0 |
| Phase 2 | $4 | $10 |
| Phase 3 | $4 | $10 |
| Phase 4 | $0 | $0 (skipped) |
| Phase 5 | $1 | $5 |
| **Committed** | **$14** | **$35** |
| **Reserve** | | **$165–186** |
| **Hard cap** | | **$200** |

The $165–186 reserve covers: re-runs after bugs, re-launching preempted spot instances, fallback model retrains if Qwen3-1.7B-Base underperforms, expanded synthetic data, additional eval beyond 200 tasks, infra mistakes (forgot to shut down a GPU, etc.), or — at user authorisation — re-enabling Phase 4 GRPO if v1 dramatically misses bar.

---

## Spend Rules

1. **Every cloud transaction logged in `BUDGET_LOG.md`** within the same Claude Code turn
2. **Single transaction > $30** requires explicit user confirmation in-session
3. **Total spend > $150** triggers a re-plan checkpoint with user
4. **All RunPod instances must have auto-shutdown on training completion** (`shutdown -h now` in startup script)
5. **Idle GPU > 30 min = shutdown via RunPod CLI** (Claude Code monitors)
6. **No closed-API teachers (Claude/GPT-5)** — open teachers only via hosted-inference providers
7. **Free tiers exhausted before paid:** Kaggle T4 + Colab T4 + HF inference free for any task that fits

---

## Cost Reduction Levers (already applied vs prior plan)

| Lever | Saving |
|---|---|
| RunPod A100 40GB Community vs Lambda A100 spot | 60% per hour |
| Qwen3-Coder-Next via Together AI vs self-host | ~$25 |
| Skip Phase 4 GRPO | $50 |
| Eval reduced from 250 → 200 tasks | ~$5 |
| Sequence length 4K vs 8K (faster training) | ~30% per hour |
| 2 hyperparameter configs vs 3 | ~$5 |
| **Total saving from prior plan** | **~$120** |

---

## Cost Tracking File

`BUDGET_LOG.md` is the live ledger. Every cloud-GPU instance launch + every shutdown logs:

```
| date | phase | what | hours | rate | cost | running_total |
| 2026-05-12 | 0 | RunPod A100 40GB — baseline run Qwen3-1.7B-Base | 1.0 | $0.60 | $0.60 | $0.60 |
```

Running total never exceeds $200 without user re-authorisation. >$30 single transaction = pause and ask.
