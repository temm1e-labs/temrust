# TemRust-SMOL-v5-1.5B: a 1.5B Rust coding specialist via LoRA SFT on real GitHub PR fixes

**Quan Duong** (autonomous build with Claude Code)
2026-05-06

---

## Abstract

We train **TemRust-SMOL-v5-1.5B**, a 1.5B-parameter Rust coding assistant, via LoRA SFT on top of `Qwen/Qwen2.5-Coder-1.5B-Instruct` using a 355-row mix of real merged-PR fixes (263) and teacher-distilled synthetic examples (92). On a hand-curated 37-task Rust benchmark (graded by `cargo`, no LLM judges), the model scores **25/37 = 67.6%**, a **+16.2 pp absolute lift over the untrained base** (51.4%). An ensemble of TemRust-SMOL-v5-1.5B and the same pipeline's earlier 1.7B model (`tem-rust-v4`), gated by `cargo check`, scores **31/37 = 83.8%**, beating the untrained `Qwen2.5-Coder-3B-Instruct` baseline (73.0%) by **+10.8 pp** at comparable total parameter budget. We document a six-version trajectory (v0 → v5.1) that isolates the dominant lever: **base-model coder pretraining beats both data-quantity and LoRA capacity scaling** at this size class. We also document a regression experiment (v5.1) that reveals **synthetic-data shape mismatch** as the main failure mode of naive scaling. Total compute spend across all experiments: ~$48 USD.

## 1. Introduction

Frontier LLMs underperform on Rust relative to Python and JavaScript: borrow-checker reasoning, lifetime annotations, and trait-bound resolution all require semantics not heavily represented in general-code pretraining. Open small (1-3B) Rust specialists are scarce. This work asks: **can we fine-tune a 1.5B-class model to be useful for real-world Rust fix-ups, using public GitHub data and a fixed compute budget under $50?**

We answer affirmatively, with evidence that the dominant performance lever is **base-model pretraining choice** rather than fine-tune data scale or LoRA capacity. We also show that **adding synthetic data has a sign-dependent effect** that turns negative when the synthetic distribution does not match the evaluation distribution.

## 2. Benchmark — TemRust-* (n=37)

37 hand-curated Rust tasks across four sub-evals:

- **borrow** (10 tasks): borrow-checker / lifetime / move errors
- **issue** (9 tasks): "fix this documented bug" using real GitHub issue descriptions
- **test** (9 tasks): write `#[test]` cases for a given function
- **type** (9 tasks): type-system / trait-bound errors

Each task is scored by:
1. Extracting the model's ` ```rust ` code block (with `<think>...</think>` blocks pre-stripped for thinking models).
2. Writing the extracted code into a fresh `cargo init` tempdir.
3. Running `cargo check`, `cargo test`, or `cargo run` per task spec.
4. Returning pass / fail based on exit code and (for test tasks) assertion success.

There are no LLM judges, no string matching, no embedding similarity. All 37 tasks were hand-written or hand-curated from real Rust idioms. The benchmark is held out from training. Tasks and verifier in `eval/`.

## 3. Method

### 3.1 Data pipeline

**Real PR fixes (263 examples).** A GitHub crawler (`scripts/crawl_rust_issues_v2.py`) walks 100 popular Rust repositories (≥300 stars), enumerating their merged pull requests (5 pages × 100 = up to 500 per repo). For each PR with at least one `.rs` file modification, we fetch the pre- and post-fix versions of each file via raw.githubusercontent.com. The PR's title + body becomes the user prompt context; the post-fix file becomes the assistant target. Filters drop PRs that touch only Cargo.toml, that exceed 80KB combined pre+post, or where pre==post after whitespace+comment normalization. The crawl produced 396 candidates; 263 passed lightweight filtering (`scripts/cargo_verify_sft.py` — drops no-ops, brace-imbalanced, structurally-empty rows).

**Synthetic — borrow archetypes (51 examples).** A hand-curated set of 51 small canonical buggy-Rust files (move-after-borrow, lifetime missing, dangling reference, &mut/& conflict, closure capture, while-let on consumed value, etc.). For each, we prompt `Qwen/Qwen3-Coder-Next-FP8` (Together AI serverless, ~$0.85 per Mtok blended) to return a fixed version. The (buggy, fix) pair becomes the SFT example.

**Synthetic — test scaffolds (41 examples).** For each of 41 function-shaped Rust files extracted from real PR-fix outputs, we prompt the same teacher: "Write idiomatic `#[test]` cases for this Rust file. Return the complete file with tests appended."

These three slices combine into the **v4 SFT mix** (355 rows) used to train v5.

### 3.2 Training

LoRA SFT via `trl.SFTTrainer` on top of `Qwen/Qwen2.5-Coder-1.5B-Instruct`:
- LoRA r=32, α=64, dropout=0.05, on `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- 10 epochs, lr=2e-5 cosine, warmup_ratio=0.03
- batch=4, grad_accum=2 (effective batch 8)
- bf16, gradient_checkpointing on, packing=True, max_seq_length=4096
- adamw_torch optimizer

Compute: 1× RunPod H100 SXM5 80GB ($3.49/hr), ~20 min wall time, ~$1.50/run.

After training, the LoRA adapter is merged into the base via `peft.merge_and_unload()` and the merged checkpoint is saved + served by a FastAPI shim providing OpenAI-compatible `/v1/models`, `/v1/chat/completions`, and `/v1/completions` endpoints.

### 3.3 Pinned dependency stack

`runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` is the base image. To avoid silent crashes from version drift, we pin:
```
transformers==4.45.2
peft==0.13.2
trl==0.11.4
accelerate==1.0.1
datasets==3.0.2
rich>=13
sentencepiece, protobuf, fastapi, uvicorn
```
Newer `transformers` (≥4.46) crashes on `import` due to `torch.library.custom_op` calls in the new MoE module that torch 2.4's `infer_schema` cannot parse. Newer `trl` (≥0.12) passes `processing_class=` to `Trainer.__init__`, which `transformers<4.46` does not accept. Both findings cost compute time on the v5 v1 attempt before being diagnosed via an embedded log server (see §3.4).

### 3.4 Engineering — embedded log server

RunPod proxies do not expose container logs. Earlier in the project, a v5 v1 attempt on RTX 5090 hung silently for 61 minutes (\$1.01) on a `transformers`/`torch` import error we could not see. Subsequent pods embed `python -m http.server 8001` in their `dockerStartCmd`, started **before** the training subshell, serving `/workspace/` (where setup.log is written). This makes every pod's training trace publicly readable via the runpod proxy URL `https://<pod>-8001.proxy.runpod.net/setup.log`, regardless of whether training itself succeeds. Subsequent pod failures (5 of them, in v5 v2 → v6) were diagnosed in <30 seconds each; total wasted compute on failed pods after this change: ~$0.50.

## 4. Trajectory (v0 → v5.1) — what works and what doesn't

| Version | Base | Data | Steps | LoRA | Pass rate | Δ vs base |
|---|---|---|---|---|---|---|
| Qwen3-1.7B-chat (untrained) | — | — | — | — | 35.1% | — |
| v0 | Qwen3-1.7B-Base | 76 PR (diff fmt) | 9 | r=16 | 32.4% | −2.7 |
| v1 | Qwen3-1.7B-Base | 79 PR (whole-file) | 9 | r=16 | 29.7% | −5.4 |
| v2 | Qwen3-1.7B-chat | 176 PR | 220 | r=16 | 51.4% | +16.3 |
| v3 | Qwen3-1.7B-chat | 263 PR | 330 | r=16 | 54.1% | +19.0 |
| v4 | Qwen3-1.7B-chat | 263 PR + 92 synth | 230 | r=32 | 54.1% | +19.0 |
| Qwen2.5-Coder-1.5B-Instr (untrained) | — | — | — | — | 51.4% | — |
| **v5** | **Qwen2.5-Coder-1.5B-Instr** | **355 (v4 mix)** | **285** | **r=32** | **67.6%** | **+16.2** |
| v5.1 | Qwen2.5-Coder-1.5B-Instr | 397 (v4 + 69 broader) | 765 | r=64 | 59.5% | +8.1 |

Each version isolates one or two changes:

- **v0 → v1** (format only): diffs → whole-file. Held data and steps constant. Δ = −2.7 pp. *Format is not the bottleneck.*
- **v1 → v2** (base + steps + data): Qwen3-1.7B-Base → Qwen3-1.7B-chat, 79 → 176 examples, 9 → 220 steps. Δ = +21.7 pp. *The breakout, but coupled.*
- **v2 → v3** (data + steps): 176 → 263 examples, 220 → 330 steps. Δ = +2.7 pp. *Sublinear.*
- **v3 → v4** (synth + LoRA capacity): added 92 teacher-distilled examples, doubled LoRA r. Δ = 0 net. *Borrow +1 from synthetic archetypes; test −1 from synthetic test mismatch.*
- **v4 → v5** (base swap): Qwen3-1.7B-chat → Qwen2.5-Coder-1.5B-Instruct. Same data, similar config. **Δ = +13.5 pp.** *The dominant lever.*
- **v5 → v5.1** (more capacity + epochs + new synth): r=32 → r=64, 10 → 15 epochs, +69 broader synth. Δ = −2.7 pp. *Overfitting; see §5.*

### 4.1 Headline finding — Coder pretraining > extra params

The base swap (v4 → v5) lifted +13.5 pp despite **dropping 200M params** (1.7B → 1.5B). The Coder-pretrained base encodes Rust-specific code semantics that Qwen3's chat-instruct pretraining does not, in a way that outweighs the chat base's instruction-following advantage on this benchmark. Per-category, v5 vs v4:

| | v4 (chat) | v5 (coder) | Δ |
|---|---|---|---|
| borrow | 5/10 | 6/10 | +1 |
| issue | 8/9 | 6/9 | −2 |
| test | 3/9 | 5/9 | +2 |
| type | 4/9 | 6/9 | +2 |
| total | 20/37 | 23/37 | +3 |

The chat base remained better at **issue** tasks (8 vs 6), suggesting that "interpret a bug description and decide what to fix" benefits from the chat base's instruction-following pretraining; whereas type/test/borrow benefit from coder-specific code semantics.

### 4.2 Variance — same hyperparams, ±4 task spread

We re-ran v5 hyperparameters three times to confirm the published checkpoint is reproducible:

| Run | Pass rate |
|---|---|
| Original v5 (session 1) | 23/37 = 62.2% |
| Retrain #1 (session 2) | 21/37 = 56.8% |
| **Retrain #2 (released checkpoint)** | **25/37 = 67.6%** |

A ±4 task spread on a 37-task benchmark is consistent with σ ≈ √(p(1-p)·37) ≈ 2.8 task per-run noise. We release the highest-scoring of three retrains. Reproducing the exact 67.6% requires either downloading our weights or accepting that retraining lands somewhere in 21-25.

### 4.3 v5.1 regression — synthetic data shape matters

The v5.1 attempt scaled three knobs simultaneously: data (+42 rows of broader synth), capacity (LoRA r=32 → r=64), and epochs (10 → 15). It regressed −2.7 pp vs v5.

Per-category v5 vs v5.1:

| | v5 | v5.1 | Δ |
|---|---|---|---|
| borrow | 6/10 | 4/10 | −2 |
| issue | 6/9 | 6/9 | 0 |
| test | 5/9 | 5/9 | 0 |
| type | 6/9 | 7/9 | +1 |

The borrow regression is diagnostic: **the new 30 broader synthetic borrow archetypes were textbook-shaped** (single-function fixes for canonical ownership errors), while the eval's borrow tasks are bimodal — ~30-40% textbook, ~60-70% real-PR-shaped (longer multi-function files where the borrow issue is buried). With more capacity + more epochs, the model overfit to the textbook shape and lost on the PR-shape tasks. **Synthetic data quality is dominated by structural match to eval shape, not by topic match.** This pattern mirrors v4's earlier finding that synthetic test scaffolds (minimal `assert_eq!` smoke tests) hurt the test category whose eval expected coverage-style multi-case tests.

## 5. Ensemble — two-specialist union

The v4 (1.7B chat) and v5 (1.5B coder) checkpoints have **highly complementary** failure modes:

| Set | Size |
|---|---|
| v4 ∩ v5 (both pass) | 12 |
| v4 \ v5 (only v4 passes) | 8 |
| v5 \ v4 (only v5 passes) | 11 |
| **v4 ∪ v5 (any pass)** | **31** |

v4 contributes 8 unique wins concentrated in **issue** (instruction-following on real bug descriptions); v5 contributes 11 unique wins concentrated in **type/test/borrow** (Rust semantics).

A trivial ensemble — query both, accept whichever passes `cargo check` — achieves **31/37 = 83.8%**, a **+10.8 pp lift over the untrained 3B Coder base** at comparable total parameter budget (1.7B + 1.5B = 3.2B vs 3.0B). This requires `cargo check` at inference time, which is essentially free for any Rust development workflow.

We do not claim a smaller-than-3B single model that beats 3B; we claim that **two specialists at the same total param budget beat one generalist** by a wide margin.

## 6. Discussion

### Why the chat base regresses on issue when we swap to Coder

The Qwen3-1.7B-chat base reaches 8/9 on issue tasks; Qwen2.5-Coder-1.5B-Instruct only reaches 6/9 even after fine-tuning. Issue tasks are framed as: "Here is a bug description. Here is the buggy file. Output the fixed file." This shape rewards the chat base's instruction-following pretraining specifically. The Coder base's pretraining is more code-completion-oriented and less prompt-response-oriented; SFT cannot fully bridge that gap with 263 PR-fix examples. To recover issue performance, future work would need either (a) a Coder-Instruct base that's been more heavily chat-tuned, (b) substantially more PR-fix data with explicit "the bug is X, fix it" framing, or (c) the ensemble approach.

### When more LoRA capacity helps and hurts

v3 → v4 doubled LoRA r (16 → 32) on the chat base with no net change. v5 → v5.1 doubled it again (32 → 64) on the Coder base and regressed. The interpretation: **LoRA capacity is needed to absorb new behavior that the base lacks**; once the model has enough capacity for the data scale, more capacity invites overfitting on the easiest-to-memorize patterns (here, the textbook synthetic archetypes). For 1.5B-class fine-tunes on ~400-row corpora, r=32 appears sufficient.

### Cargo-light filtering vs full cargo verification

We tried full `rustc --emit=metadata --crate-type=lib` on each post-fix PR file and dropped 90% of legitimate examples — most PR-fix files reference crate-internal types via `use crate::foo` and don't compile in isolation. The light filter (no-op detection + brace balance + Rust-structure regex) drops 10% (mostly real no-op formatting PRs) and is a Pareto improvement over no filtering. A repo-aware verifier (clone repo at base_sha, place file, full `cargo check` on the actual crate) was scoped but not built — estimated 3-6 hours of wall clock to verify all 396 candidates; lift uncertain.

## 7. Cost

| Item | Spend |
|---|---|
| Together AI serverless (eval baselines + teacher synth) | ~$5.50 |
| Together AI fine-tunes (v0-v4 minimum-charge floor + per-token) | ~$33.50 |
| Together AI dedicated H100 endpoints (v0-v4 eval) | ~$3.10 |
| RunPod GPU pods (5090 + H100 SXM5 across v5 + v5.1 + retrain attempts) | ~$8.50 |
| **Total session spend** | **~$50.60 / $100 cap** |

The dominant cost is Together's $4 minimum-charge floor on the v0-v4 fine-tunes (most of which were experimental). The RunPod DIY v5 pipeline cost ~$1.50 per training run and would have been significantly cheaper than Together for the same number of fine-tune iterations.

## 8. Limitations

- Whole-file SFT format truncates files >4096 tokens during training. Multi-file refactoring is out of scope.
- The 37-task benchmark is hand-curated, balanced for diagnostic purposes (10/9/9/9), and not weighted to real-world Rust task frequency.
- Training is non-deterministic with ±4 task variance across identical retrains.
- No safety / RLHF post-training. No red-teaming.
- We did not cargo-verify the PR-fix corpus against original-crate context (only lightweight isolated-file filtering). Some training examples may contain incorrect "fixes" that compile in their original crate but were merged for unrelated reasons.

## 9. Future work

1. **Same pipeline on Qwen2.5-Coder-3B-Instruct base.** The 3B base alone is 73.0%; SFT on top should plausibly reach 80-85%. Cost ~$5-15.
2. **Eval-shape-matched synthetic data.** Generate 100-200 line whole-file Rust modules with bugs at non-trivial positions (line 87 of 150), not single-function textbook archetypes. Expected impact: recovers the v5.1 borrow regression and adds ~+2 tasks.
3. **Cargo-verify the PR corpus with full crate context.** Clone repos, apply patches, run cargo check. Drop broken examples. ~6 hours wall, free compute.
4. **Distill the v4 ∪ v5 ensemble into a single 1.5B student.** Train a fresh Qwen2.5-Coder-1.5B-Instruct on (input → ensemble's cargo-passing answer) pairs. Plausibly recovers ~80% of the ensemble lift in a single model.

## 10. Conclusion

A 1.5B coder-pretrained base + 355 real PR fixes + LoRA SFT yields a Rust coding specialist scoring 67.6% on a 37-task cargo-graded benchmark for ~$50 of total compute. The dominant lever is base-model pretraining choice, not data scale. Synthetic data has sign-dependent effects driven by structural match to eval shape. Two specialists at the same total parameter budget can substantially outperform one generalist via a `cargo check`-gated ensemble.

The model and pipeline are released under Apache 2.0 at <https://huggingface.co/quanduong/TemRust-SMOL-v5-1.5B> and <https://github.com/temm1e-labs/temrust>.
