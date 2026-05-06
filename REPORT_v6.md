# Tem-Rust v6 IQmax — Final Report

**Date:** 2026-05-06 evening
**Hypothesis tested:** Does training a 1.5B Coder model on dense academic-reasoning content (math, CS theory, type theory, programming language semantics) lift Rust task performance via general-reasoning transfer?

## TL;DR

**Hypothesis not confirmed.** Across three identically-configured retrains, the best v6 IQmax variant scored **24/37 = 64.9%**, which is **−1 task below** the v5 release (25/37 = 67.6%). v6 was **NOT released**.

The negative result is informative: it strengthens the v0 → v5 finding that **synthetic data shape matters more than topic richness**, and adds new evidence about training-time variance under mixed-domain SFT.

## Setup

- **Base:** Qwen/Qwen2.5-Coder-1.5B-Instruct (same as v5)
- **Hyperparameters:** LoRA r=32, α=64, 10 epochs, lr=2e-5, batch=4 grad_accum=2, packing=True, max_seq_len=4096 (identical to v5)
- **Data:** v5's 355-row mix + 170 dense reasoning Q&A pairs = **525 rows total**
- **Synthetic source:** Qwen3-Coder-Next-FP8 teacher generated rigorous step-by-step explanations for 170 hand-curated topics across 7 domains:
  - type-theory (32): System F<:, Hindley-Milner, GADTs, dependent types, Curry-Howard, lifetime calculus, ...
  - rust-systems (28): LLVM IR, GC, MESI cache coherence, NUMA, async/await, lock-free DSes, ...
  - pl-semantics (25): operational/denotational semantics, CEK machine, CPS, ANF, separation logic, ...
  - algo-complexity (25): Master theorem, NP-completeness, Chernoff bounds, FPT, ETH, fine-grained complexity, ...
  - math-reasoning (24): probabilistic method, martingales, CLT, Chernoff, Borel-Cantelli, ...
  - cat-theory (20): Yoneda, monads, adjunctions, Kan extensions, profunctors, ...
  - foundations (16): Gödel incompleteness, halting problem, Curry-Howard, Church-Rosser, ...
- **System prompt for IQ slice:** Distinct from v5's Rust-fix system prompt — "careful, technically rigorous coding and reasoning assistant," to avoid the model learning to wrap explanations in ` ```rust ` blocks.
- **Training:** 3 parallel pods on RunPod H100 SXM5 80GB, ~25 min each
- **Cost:** ~$1 teacher + ~$5 RunPod (3 train + 3 eval) = ~$6 total

## Per-variant results (3 retrains, identical config)

| variant | borrow | issue | test | type | total | rate |
|---|---|---|---|---|---|---|
| A | 6/10 | 6/9 | 4/9 | **8/9** | 24/37 | 64.9% |
| B | 5/10 | 6/9 | 3/9 | 5/9 | 19/37 | 51.4% |
| C | 5/10 | 7/9 | 5/9 | 6/9 | 23/37 | 62.2% |
| **v5 published** | **7/10** | **7/9** | 4/9 | 7/9 | **25/37** | **67.6%** |
| **best v6 vs v5** | −1 | −1 | 0 | **+1** | **−1** | **−2.7 pp** |

## What we learned

### 1. The variance is wider with mixed-domain data

v5's three retrains spanned 21-25 (range 4). v6's three retrains spanned **19-24 (range 5)**, with one variant (B) regressing all the way to the untrained Coder-1.5B base (51.4%). Mixing reasoning prose into the SFT corpus made some training runs **erase** v5's lift entirely.

This is a real result: **adding more diverse training data did not stabilize training, it destabilized it**. Likely cause: with a separate system prompt and a different response shape (long prose vs ```rust block), the IQ slice creates two competing modes, and the optimizer under random init occasionally lands closer to the IQ mode at the expense of the Rust mode.

### 2. Type category genuinely improved (best variant)

v6-A scored **8/9 on type** — the highest in any version. Type-theory and trait-bound questions made up the largest fraction of the IQ corpus (32 of 170), so it makes sense that an IQ-trained model would specifically improve on type-system reasoning. **The hypothesis is partially true**, just not net-positive on the eval as a whole.

### 3. Borrow regressed

v6-A scored only 6/10 on borrow vs v5's 7/10. The model was distracted from the borrow-checker pattern by other content. Pattern matches v4 → v5.1 where adding more synthetic data also regressed borrow.

### 4. The shape-mismatch finding holds

This is the third experiment (v4 synthetic tests, v5.1 broader synthetic, v6 IQ prose) where adding synthetic data with a *different shape* than the eval has produced a regression on at least one category. The lesson is consistent: **synthetic SFT data must match the response shape of the eval to be net-positive**.

## Decision

Per the release condition (≥ v5's 25/37), v6 was **not released**. v5 stays as the published model on HuggingFace.

The IQ-max corpus and pipeline are committed to the repo for reproducibility:
- `scripts/synth_iqmax.py` — generates the 170-topic dense Q&A
- `data/clean/sft_iqmax.jsonl` — the 170 generated examples
- `data/clean/sft_v6_iqmax.jsonl` — combined 525-row v6 mix
- `scripts/runpod_train_coder_v6.py` — H100 launcher with v5 hyperparams + v6 data
- `eval/results/tem-rust-iqmax_{A,B,C}__*.json` — three eval result files

## What I would try next if extending the iqmax thesis

1. **Match shape, not just topic.** Generate the IQ content as `{system: Rust-fix, user: Rust file with comment "explain why this fails", assistant: rust-block-with-explanatory-comments}`. Keep the Rust ```rust shape on every assistant turn.
2. **Smaller IQ injection, weighted by eval-relevance.** Drop most of the cat-theory / foundations slices, double down on type theory + Rust systems + PL semantics where the hypothesis is most plausible.
3. **Ablate the IQ system prompt.** Test whether using v5's system prompt for the IQ slice (forcing the persona to be unified) changes the variance.
4. **Increase corpus size dramatically.** 170 IQ rows in 525 total = 32% of the corpus by row count. May not be enough signal to reliably move evals; but at higher fractions the destabilization may worsen further.

## Cumulative session spend

After v6: **~$53 / $100 (53%)**. All RunPod and Together resources confirmed stopped.

## Files

- `eval/results/tem-rust-iqmax_A__1778066129.json` — v6 variant A, 24/37
- `eval/results/tem-rust-iqmax_B__1778066131.json` — v6 variant B, 19/37
- `eval/results/tem-rust-iqmax_C__1778066132.json` — v6 variant C, 23/37
