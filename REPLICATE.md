# REPLICATE — Tem-Rust as-executed pipeline

This is the **actually executed** pipeline that produced Tem-Rust v0/v1/v2/v3/v4. It diverges from the original plan in `PIPELINE.md` (which assumed Lambda + Axolotl + GRPO); the as-executed flow is Together AI hosted fine-tune + manual ChatML inference. Pipeline is **base-model agnostic** — the same recipe targets 3B / 7B / 14B by changing one argument.

For the design rationale and lesson-by-lesson trajectory, see `REPORT_2026-05-06.md`. This file is the ops manual.

---

## Architecture

```
GitHub PRs (top 100 Rust repos)
    │
    │ scripts/crawl_rust_issues_v2.py  (REST + auth, paginated, ~80 min)
    ▼
data/raw/issue_candidates_v3.jsonl  (~400 PR records, gitignored)
    │
    │ scripts/sft_to_wholefile.py  (raw.githubusercontent.com fetch, ~3 min)
    ▼
data/clean/sft_wholefile_v3.jsonl  (263 whole-file SFT rows)
    +
data/clean/sft_synthetic.jsonl  (92 synthetic rows from teacher distillation)
    │  scripts/synth_data.py  (Qwen3-Coder-Next teacher, ~25 min)
    ▼
data/clean/sft_wholefile_v4.jsonl  (355 mixed rows, shuffled)
    │
    │ Together /v1/files (upload), /v1/fine-tunes (LoRA SFT, ~15 min)
    ▼
quanduong/Qwen3-1.7B-tem-rust-v4-XXXXXX  (HF model name)
    │
    │ Together /v1/endpoints (1× H100 SXM, 5-25 min warmup)
    ▼
endpoint name: <model>-YYYYYY  (.name field — the suffix matters)
    │
    │ eval/runner.py via together-base provider
    │   └── eval/clients.py:TogetherBaseClient
    │       (manual Qwen3 ChatML wrapper + retry+backoff)
    │   └── eval/verifiers.py
    │       (fresh cargo project per task, 60s timeout)
    ▼
eval/results/tem-rust-v4__<unix-ts>.json  (37-task TemRust-* result)
    │
    │ scripts/stop_endpoint.py  (CRITICAL — H100 idle = $4/hr)
    ▼
endpoint state=STOPPED, billing halted
```

## Trajectory & lessons

| version | base | data sources | examples | gradient steps | LoRA | result | takeaway |
|---|---|---|---|---|---|---|---|
| v0 | Qwen3-1.7B-**Base** | PR-fix **diff**     | 76  | 9   | r=16 | 32.4% | regression vs base (35.1%) |
| v1 | Qwen3-1.7B-**Base** | PR-fix **whole-file** | 79  | 9   | r=16 | 29.7% | format swap didn't help → format isn't the bottleneck |
| v2 | Qwen3-1.7B (chat)   | PR-fix whole-file   | 176 | 220 | r=16 | **51.4%** | breakout: chat-base + 24× more steps + 2× data |
| v3 | Qwen3-1.7B (chat)   | PR-fix whole-file   | 263 | 330 | r=16 | **54.1%** | +50% data → only +1 task. data scaling sublinear. |
| v4 | Qwen3-1.7B (chat)   | PR-fix + synthetic test/borrow | 355 | ~450 | r=32 | TBD | mixed sources + double LoRA capacity |

Two load-bearing negative results:

1. **v0 → v1 (controlled format A/B):** swapping diff format for whole-file format with everything else held constant *did not* improve the model. This proves training-data format is not the bottleneck at this data scale; we wasted 0.5 days on the format hypothesis.
2. **v2 → v3 (controlled data scale-up):** +50% examples / +50% steps gave +1 task. The PR-fix corpus has narrow diversity — open-source bug fixes cluster around a small set of archetypes. More of the same hits sublinear scaling.

What broke through (v1→v2): chat base instead of raw Base + ~24× more gradient steps + ~2× data, all together.
What v4 attempts: different signal (test-generation, borrow archetypes) since more PR-fix data has plateaued.

## Reproduction recipe

### 0. Prerequisites

- `~/.config/temllm/` with chmod-600 env files: `hf.env`, `together.env`, `gh.env`, `runpod.env` (each `export VAR=...`)
- Python 3.14 venv at `.venv/` with `requests together huggingface_hub`
- Cargo / rustc toolchain (for cargo-graded eval verifier)
- Together AI account (~$25 covers v0–v3; ~$15 more for v4 = **~$40 total**)
- RunPod account (~$5 covers all baselines)
- GitHub PAT with `public_repo` scope for the crawler

### 1. Crawl PR candidates

```bash
source scripts/load_creds.sh
python scripts/crawl_rust_issues_v2.py \
    --max-repos 100 --max-prs-per-repo 30 --pages 5 \
    --out data/raw/issue_candidates_v3.jsonl
```

Filters: stars >300, pushed >2024-06, must reference an issue with `fix/close/resolve`, single .rs file change preferred, 30 ≤ diff_lines ≤ 1500. ~80 min wall clock for ~400 candidates from ~35 repos. The crawler writes incrementally; you can kill it at any point.

### 2. Build whole-file SFT

```bash
python scripts/sft_to_wholefile.py \
    --input data/raw/issue_candidates_v3.jsonl \
    --output data/clean/sft_wholefile_v3.jsonl
```

Fetches pre-fix file at `base_sha` and post-fix at `merge_commit_sha` from `raw.githubusercontent.com`. Filters by combined-bytes cap (default 80KB → ~20K tokens; fits comfortably in Qwen3-1.7B's 32K context). Yields ~265 SFT rows from ~400 candidates (≈30% drop to too-big files).

### 3. Generate synthetic test + borrow data

```bash
python scripts/synth_data.py --test-cap 50
```

Two slices:
- **Test-generation (~40 examples).** For each function-shaped file from v3 SFT, ask `Qwen/Qwen3-Coder-Next-FP8` (teacher; 88.9% on TemRust-*) to add a `#[cfg(test)] mod tests` block. Pairs original file (input) with teacher's tested file (output).
- **Borrow/lifetime (~50 examples).** 51 hand-curated buggy Rust archetypes (move-after-borrow, missing lifetime, &mut/& conflict, dangling reference, iterator consumes vec, closure capture, Vec<&str> from String, etc.) → teacher fix.

Cost: ~$1 of teacher tokens (Together serverless, $0.50 in / $1.20 out per Mtok). ~25 min wall time. Script flushes each row immediately so you can kill it without losing progress.

### 4. Combine + shuffle for v4

```bash
python -c "
import json, random
out = []
for p in ['data/clean/sft_wholefile_v3.jsonl', 'data/clean/sft_synthetic.jsonl']:
    out.extend(line.strip() for line in open(p) if line.strip())
random.seed(42); random.shuffle(out)
open('data/clean/sft_wholefile_v4.jsonl', 'w').write('\n'.join(out) + '\n')
"
```

### 5. Fine-tune

```bash
python -c "
import os
from together import Together
c = Together(api_key=os.environ['TOGETHER_API_KEY'])
f = c.files.upload(file='data/clean/sft_wholefile_v4.jsonl', check=True)
ft = c.fine_tuning.create(
    model='Qwen/Qwen3-1.7B',                 # the chat model (not -Base)
    training_file=f.id,
    n_epochs=10, batch_size=8,                # bs<8 rejected by Together for this base
    learning_rate=2e-5,
    lora=True, lora_r=32, lora_alpha=64,      # double v2/v3 capacity for diverse signal
    n_evals=0,
    suffix='tem-rust-v4',
)
print(ft.id, ft.model_output_name)
"
```

~15 min wall clock for v4-scale (355 ex × 10 epochs ≈ 450 steps, ~20M training tokens). Cost: $4 minimum-job floor binding for ≤~10M training tokens, real $0.40/Mtok pricing thereafter (v3 was $8.50, v4 ≈ $13).

### 6. Deploy dedicated H100 endpoint

```bash
python -c "
import os
from together import Together
c = Together(api_key=os.environ['TOGETHER_API_KEY'])
ep = c.endpoints.create(
    model='quanduong/Qwen3-1.7B-tem-rust-v4-XXXXXX',  # the model_output_name
    hardware='1x_nvidia_h100_80gb_sxm',
    autoscaling={'min_replicas': 1, 'max_replicas': 1},
    inactive_timeout=15,
    display_name='Tem-Rust v4',
)
print(ep.id, ep.name)  # name has -YYYYYY suffix; use this for inference, NOT model_output_name
"
```

H100 SXM is **$0.0665/min ($3.99/hr)**. Endpoint takes 5-25 min to reach `STARTED|ready=1/1`.

### 7. Evaluate

```bash
python -m eval.runner \
    --model quanduong/Qwen3-1.7B-tem-rust-v4-XXXXXX-YYYYYY \  # use endpoint .name
    --provider together-base \
    --out eval/results/tem-rust-v4__$(date +%s).json
```

Use `together-base` (not `together`) because Together's `/v1/chat/completions` route 400s on dedicated endpoints regardless of base. The `together-base` client uses `/v1/completions` with a manually formatted Qwen3 ChatML prompt. See `eval/clients.py:TogetherBaseClient.chat` — it includes retry+backoff (5 attempts, 1-16s exponential) for the `dedicated_endpoint_not_running` flap that occurs ~1 task in 5 even when autoscaling reports `STARTED|ready=1/1`. Without retries, expect to lose ~5-10 tasks to spurious endpoint blips.

### 8. Stop endpoint (CRITICAL)

```bash
python scripts/stop_endpoint.py <endpoint-id>
```

Each minute idle is $0.0665. Forgetting this for one weekend would cost $383. Always verify `state=STOPPED` after the call.

## Extending to bigger base models

The pipeline is base-model agnostic. To target Qwen2.5-3B, Qwen2.5-7B-Instruct, etc.:

1. **Verify Together fine-tune support.** `client.models.list()` and look for the target. As of 2026-05: Qwen3-0.6B, Qwen3-1.7B, Qwen3-1.7B-Base, Qwen2.5-1.5B, Qwen2.5-1.5B-Instruct, Qwen2.5-3B-Instruct, Qwen2.5-7B-Instruct, Qwen2.5-32B are fine-tune bases. Qwen2.5-Coder-1.5B is **not** (model exists but not as fine-tune base).
2. **Adjust batch size.** Together's `min_batch_size` varies by model. v4 used bs=8 (the floor for Qwen3-1.7B); a 7B may permit smaller. If `client.fine_tuning.create(...)` raises `ValueError: Requested batch size of N is lower than the minimum allowed value of M`, bump to M.
3. **Adjust LoRA rank.** Bigger models can absorb higher rank. r=32-64 for ≥3B is reasonable. Lower if you want a smaller adapter for distribution.
4. **Endpoint hardware.** 7B fits on `1x_nvidia_h100_80gb_sxm`; 32B+ likely needs 2x or 4x. Check with `client.endpoints.list_hardware()`.
5. **Eval `max_tokens`.** `eval/runner.py:run_one` uses 8192 currently. Bump if outputs truncate on bigger models.
6. **Inference path.** Bigger chat models may also need `together-base` — Together's `/v1/chat/completions` route on dedicated endpoints has been unreliable across model sizes in our testing.

The data is reusable as-is — same JSONL Together-chat format works across all Qwen variants. Crawl can be re-run with the same script for a fresh corpus.

## File map

| path | purpose |
|---|---|
| `scripts/crawl_rust_issues_v2.py` | GitHub PR crawler (looser filter, paginated) — supersedes `crawl_rust_issues.py` |
| `scripts/sft_to_wholefile.py` | converts PR candidates to whole-file SFT format |
| `scripts/synth_data.py` | teacher distillation for test-gen + borrow archetypes |
| `scripts/together_finetune_v2.py` | fine-tune kickoff helper (CLI args; writes job id) |
| `scripts/stop_endpoint.py` | stops a Together endpoint to halt H100 idle billing |
| `scripts/runpod_baseline.py` | RunPod vllm pod launcher for non-serverless baselines |
| `eval/runner.py` | runs eval against a model id via specified provider |
| `eval/clients.py` | provider clients: `together`, `together-base`, `vllm`, `ollama` |
| `eval/extractors.py` | strips `<think>...</think>` (Qwen3) and pulls ` ```rust ` blocks |
| `eval/verifiers.py` | spawns fresh cargo project per task; runs `cargo check`/`test`/`run` |
| `eval/tasks/*.json` | 37 hand-curated Rust tasks across 4 sub-evals |
| `eval/results/*.json` | per-run eval results |
| `data/raw/issue_candidates_v3.jsonl` | crawled PR metadata + diffs (gitignored — too big) |
| `data/clean/sft_wholefile_v3.jsonl` | 263-row PR-fix SFT |
| `data/clean/sft_synthetic.jsonl` | 92-row teacher-distilled synthetic SFT |
| `data/clean/sft_wholefile_v4.jsonl` | 355-row combined v4 SFT |
| `REPORT_2026-05-06.md` | full session report (results, costs, lessons) |
| `BUDGET_LOG.md` | line-by-line cloud spend |
| `STATUS.md` | high-level project state |
| `PIPELINE.md` | original prescriptive plan (pre-execution) — kept for archival reference |
| `REPLICATE.md` | this file — as-executed pipeline |

## Theoretical ceiling for the 1.7B + LoRA approach

Per category, with PR-fix + synthetic data on Qwen3-1.7B:

| sub-eval | base | v3 | realistic ceiling | 3B bar |
|---|---|---|---|---|
| borrow | 3 | 4 | 6 | 7 |
| issue | 4 | 8 | 9 | 9 |
| test | 5 | 4 | 6 | 6 |
| type | 1 | 4 | 6 | 5 |
| **total** | 13 | 20 | **~26 = 70%** | 27 = 73% |

To break clearly above ~70% with this pipeline, the next axis to explore is **base model size** — not data, not steps, not LoRA capacity. Qwen2.5-3B-Instruct as base is the natural step (it's a Together fine-tune base; eval baseline 73.0% as a chat model would likely fine-tune to 80%+).

## Watch-outs (things that bit us)

1. **Together's $4 minimum-job-charge floor.** v0–v2 each paid $4 for ~$0.06–$2.40 of actual training tokens. Sub-experiments (LR sweep, ablations) at this regime are economically inefficient — either crank dataset size to clear the floor (v3 onwards) or move to RunPod DIY fine-tune.
2. **Together's chat-completions route 400s on dedicated endpoints.** Always use `/v1/completions` + manual ChatML wrapper.
3. **Dedicated endpoints flap mid-eval.** `dedicated_endpoint_not_running` returns even when autoscaling reports `STARTED|ready=1/1`. Always wrap with retry+backoff.
4. **RunPod RTX 4090 SECURE host pool flakiness.** ~6 of 8 hosts allocated wouldn't boot vllm/vllm-openai:v0.20.1. Workaround: RTX 5090 SECURE ($0.99/hr vs $0.69 but reliable).
5. **Base-model fine-tunes have no chat template.** If you fine-tune `Qwen3-1.7B-Base` (not chat), the resulting model will have no built-in ChatML — the eval client must apply one manually. Use `Qwen3-1.7B` (chat) as base unless you have a specific reason not to.
6. **GitHub raw rate limit.** Crawling + file fetch can both hit the 5000/hr limit. With auth (`GH_TOKEN`), it's plenty for these scales but watch for it on bigger crawls.
7. **`max_tokens=2048` truncates Qwen3 thinking models.** If you eval a thinking model and see lots of truncated `<think>` blocks, bump to 8192 (v0 lost ~8 points to this before we caught it).
