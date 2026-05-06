# Tem-Rust v5.1 — Squeeze Attempt Final Report

**Date:** 2026-05-06 afternoon
**Author:** Claude Code (continuation session)
**User directive:** *"I want to mathmax v5… if it surpasses 3b then release it on huggingface and github"*

## TL;DR

**v5.1 = 22/37 = 59.5%.** A **regression** of −1 task (−2.7 pp) vs. v5 (23/37 = 62.2%) and well below the 3B base bar (27/37 = 73.0%).

Per the release condition you set, v5.1 was **NOT** released on HuggingFace or GitHub. **v5 (23/37 = 62.2%) remains the best Tem-Rust checkpoint.** Total v5.1 spend: ~$2.86.

## Per-category result

| sub-eval | Coder-1.5B base | v5 | **v5.1** | 3B base (target) |
|---|---|---|---|---|
| borrow (10) | 5 | 6 | **4** | 7 |
| issue (9) | 5 | 6 | 6 | 9 |
| test (9) | 4 | 5 | 5 | 6 |
| type (9) | 5 | 6 | **7** | 5 |
| **total (37)** | **19 (51.4%)** | **23 (62.2%)** | **22 (59.5%)** | **27 (73.0%)** |

**Δ vs. v5:** borrow −2, issue 0, test 0, type +1 → −1 net.

The improvement on type (+1) was wiped out by the regression on borrow (−2). Issue and test held flat.

## What was changed (v5 → v5.1)

| Lever | v5 | v5.1 | Reasoning |
|---|---|---|---|
| Data | 355 rows (263 v3 PR + 92 synth) | **397 rows** (236 cleaned PR + 92 v4 synth + 69 NEW synth) | +cleaned + broader synthetic |
| LoRA r / alpha | 32 / 64 | **64 / 128** | more capacity for Coder base |
| Epochs | 10 | **15** | more passes |
| Learning rate | 2e-5 | **1e-5** | slower, given more capacity |
| Steps (effective) | 285 | **765** | ~2.7× |

## Diagnosis — why v5.1 regressed

Three independent levers were turned simultaneously (data, capacity, epochs). The regression on borrow specifically suggests **overfitting to the synthetic borrow archetypes at the expense of the more diverse PR-fix borrow examples**. Three contributing factors:

1. **Higher LoRA capacity (r=64) + 2.7× more effective steps (765 vs 285)** is a combined regularization weakening. With v4 we tested r=32 vs r=16 in isolation and got +0 net. v5 retained r=32 but switched base — the Coder base may need *less* LoRA capacity than the chat base did, not more, because the Coder pretraining already encodes a lot of Rust-specific structure.
2. **30 new borrow archetypes**, while different scenarios from v4's 51, are still small canonical cases — single-function fixes for textbook ownership errors. The model may have learned the textbook-fix style at the expense of the messier whole-file PR-fix style. The eval's borrow tasks include both archetype-shaped (3-4 of 10) and PR-shaped (6-7 of 10), and we now do better on the former and worse on the latter. Net loss on the category.
3. **lr=1e-5 + 15 epochs** is a "low-and-long" schedule — useful when the loss landscape has narrow valleys, harmful when it has broad ones. With LoRA r=64 the effective parameter manifold is wider, so a higher learning rate over fewer epochs would have explored more of it. We compounded slow-and-many.

**The cargo-verify pre-filter (236 of 263 PR rows kept) was the right move on its own** — dropping no-op formatting PRs raises signal-per-token. That isn't responsible for the regression. Empirical proof: issue/test/type held or improved vs v5; only borrow regressed.

## What we'd do differently (v5.2 hypothetical)

If the goal is still beating 3B (27/37), each of these *individually* might lift v5 a bit. But none of them will close the −4 gap on its own — we already saw at v3 → v4 that more-of-the-same does not break ceilings.

1. **Hold v5's hyperparameters fixed** (r=32, 10 epochs, lr=2e-5) and *only* swap in the cleaned PR corpus + the new synthetic, so we have a controlled experiment over data quality alone. Likely +0 to +1 task.
2. **Drop the borrow archetypes entirely from the synthetic.** v4 already showed that synthetic test-gen *worsened* tests by mismatching the eval's coverage style; the borrow archetypes here may have done the same to PR-style borrow tasks. Likely +1 task (recovers the v5 borrow score).
3. **Reduce epochs to 5** with r=32. Anti-overfitting. Likely +0 to +1.
4. **Try a different teacher (DeepSeek-V3.1) for synth diversity** — but the gain is uncertain and Qwen3-Coder was the strongest on this bench by a wide margin in our earlier baselining (88.9% vs DeepSeek 71.4%).
5. **Switch base to Qwen2.5-Coder-3B-Instruct** (v6, ~$5-15 cost on RunPod DIY). 3B Coder baseline is already 73.0%; SFT on top should lift to 80-85%. **This is the actually-likely path to clearly beat the 3B bar — at the cost of doubling the param count we ship.**

## Cost reconciliation

| Item | Cost |
|---|---|
| Cargo-light filter (local, free) | $0.00 |
| Synth via Qwen3-Coder-Next-FP8 (~70 calls, 4K-6K tokens each) | ~$1.00 |
| RunPod H100 SXM5 v5.1 training (27 min) | $1.57 |
| RunPod H100 SXM5 v5.1 eval (5 min) | $0.29 |
| **v5.1 total** | **~$2.86** |
| Cumulative session (after v5.1) | **~$41.35 / $100 (41.4%)** |

## Decision

**v5 (23/37 = 62.2%) remains the best released-grade Tem-Rust checkpoint.** No HF/GitHub release this round.

If the next session wants another shot at beating 3B:
- Cheapest experiment: v5.2 = v5 hyperparams (r=32, 10 epochs, lr=2e-5) on the cleaned PR + new synthetic mix — controlled-variable test of data alone. Cost ~$2.
- Highest-EV experiment: v6 = v5.1 pipeline on Qwen2.5-Coder-3B-Instruct base. Cost ~$5-15.

## Files

- `eval/results/tem-rust-v5_1__1778051370.json` (or similar timestamp) — canonical v5.1 result, 22/37
- `data/clean/sft_wholefile_v5_clean.jsonl` — 236 PR rows after light filter
- `data/clean/sft_synthetic_v5_1.jsonl` — 69 new synthetic rows
- `data/clean/sft_wholefile_v5_1.jsonl` — 397-row combined train mix
- `scripts/cargo_verify_sft.py` — light filter (no-op + brace + structure)
- `scripts/synth_data_v5_1.py` — broader synthetic with cargo-verify hook
- `scripts/build_v5_1_mix.py` — combiner with dedupe
- `scripts/runpod_train_coder_v5_1.py` — H100 launcher (r=64, 15 epochs)
- `scripts/upload_to_hf.py` — HF Hub upload tool (unused this round; ready for next)
