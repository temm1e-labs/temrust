# PIPELINE — Tem-Rust-1.7B Technical Execution

The exact technical recipe. Every command, every config, every file path. Designed so Claude Code executes autonomously and a future maintainer can reproduce.

---

## Stage 0 — Local Mac Bootstrap

```bash
# Tools (Mac M-series)
brew install rust git python@3.11 git-lfs ollama

# Python env
cd ~/Documents/Github/TemLLM
python3 -m venv .venv && source .venv/bin/activate
pip install unsloth==2026.5 axolotl trl vllm sglang
pip install datasets huggingface_hub wandb
pip install torch==2.6 torchvision  # MPS for local sanity checks only

# Rust toolchain (for eval verifier + CLI)
rustup default stable
cargo install bacon cargo-watch
```

Local Mac runs: data crawling, eval grading (cargo), GGUF inference smoke tests, CLI development.
Local Mac does NOT run: any training, teacher inference, batch eval.

---

## Stage 1 — Data Pipeline

### 1a. Crawl Rust GitHub issues

Script: `scripts/crawl_issues.py`
- GitHub Search API: `language:Rust stars:>100 archived:false pushed:>2025-01-01`
- Per repo: list closed PRs that reference an issue, that added a `#[test]` block
- Per PR: get the diff, the issue text, the repo state at PR base
- Output: `data/raw/issues.jsonl` (~10K candidate rows)

### 1b. Verify with cargo

Script: `scripts/verify_cargo.py`
- For each candidate: clone repo at base SHA, apply diff, run `cargo test`
- Keep only those where: target test failed before, passes after, no other tests broken
- Run in Docker for isolation; parallelise across cores
- Output: `data/clean/issues_verified.jsonl` (target: ~3K)

### 1c. Synthetic compiler errors (deferred to Phase 3)

Script: `scripts/synth_compile_errors.py`
- Take well-formed Rust file
- Apply mutations: drop `mut`, swap types, remove lifetime, wrong trait
- Run `rustc` capture error message
- Send `(broken_code, error_msg)` to teacher → get fix
- Verify with `cargo check`
- Keep only verified
- Output: `data/clean/compile_errors.jsonl` (target: ~2K)

### 1d. Test generation pairs

Script: `scripts/extract_test_pairs.py`
- For each crate: parse with `syn` (Rust AST library) via `tree-sitter-rust`
- Match `pub fn foo(...)` with `#[test] fn test_foo(...)`
- Verify the test passes when applied
- Output: `data/clean/test_pairs.jsonl` (target: ~1.5K)

### 1e. Clippy fixes

Script: `scripts/clippy_pairs.py`
- Run `cargo clippy --message-format=json` on a Rust file
- For each warning with a machine-applicable suggestion: get original + fixed version
- For non-machine-applicable: ask teacher to fix; verify with clippy
- Output: `data/clean/clippy_pairs.jsonl` (target: ~1K)

### 1f. Format + decontaminate + mix

Script: `scripts/build_sft_dataset.py`
- Convert all sources to chat format with system prompt:
  ```
  System: You are Tem-Rust, a Rust coding assistant. Use cargo to verify your work.
  User: <task description + relevant code>
  Assistant: <reasoning + diff/code/test>
  ```
- Decontaminate against `eval/temrust_*.jsonl` via:
  - Exact issue-ID match (drop)
  - Repo-level match for held-out repos (drop)
  - Embedding similarity > 0.92 (manual review)
- Mix per-source quotas: 30% issues, 25% compile errors, 20% test pairs, 15% clippy, 10% reserved for synthetic
- Output: `data/sft_v0.jsonl` and after Phase 3, `data/sft_v1.jsonl`

---

## Stage 2 — Eval Suite

### 2a. Build TemRust-* benchmark

Hand-curated, 50 tasks each. Stored in `eval/`:
- `eval/temrust_borrow.jsonl`
- `eval/temrust_type.jsonl`
- `eval/temrust_test.jsonl`
- `eval/temrust_clippy.jsonl`
- `eval/temrust_issue.jsonl`

Format per task:
```json
{
  "id": "borrow-001",
  "task": "Fix the borrow checker error in this code...",
  "input": "<rust source>",
  "verifier_cmd": "cargo check",
  "expected": "compiles cleanly",
  "metadata": {"difficulty": "easy", "source": "rustc-error-book ch3"}
}
```

### 2b. Eval runner

Script: `eval/run.py`
- Inputs: model HF id or local checkpoint, eval file
- For each task: prompt model → extract code/diff → write to scratch repo → run verifier
- Score: pass / fail / timeout (30s per task)
- Output: `eval/results/<model>__<eval>__<timestamp>.json`
- Aggregator: `eval/aggregate.py` produces leaderboard CSV

### 2c. Baseline runs (Phase 0)

```bash
for model in \
  Qwen/Qwen3-1.7B-Base \
  Qwen/Qwen3-1.7B-Instruct \
  Qwen/Qwen2.5-Coder-1.5B-Instruct \
  Qwen/Qwen2.5-Coder-3B-Instruct \
  Qwen/Qwen2.5-Coder-7B-Instruct \
  deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B; do
  python eval/run.py --model $model --eval all
done
python eval/aggregate.py > BASELINES.md
```

---

## Stage 3 — SFT (Phase 2 + Phase 3)

### 3a. Axolotl config

`configs/sft_v0.yaml`:
```yaml
base_model: Qwen/Qwen3-1.7B-Base
load_in_4bit: true
adapter: qlora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

datasets:
  - path: data/sft_v0.jsonl
    type: chat_template
    chat_template: chatml

sequence_len: 8192
sample_packing: true
pad_to_sequence_len: false

micro_batch_size: 1
gradient_accumulation_steps: 32
num_epochs: 3
optimizer: adamw_8bit
learning_rate: 2e-4
lr_scheduler: cosine
warmup_ratio: 0.03

bf16: true
flash_attention: true
gradient_checkpointing: true

output_dir: ./outputs/tem-rust-v0
hub_model_id: tem-llm/tem-rust-1.7b-v0
hub_strategy: end

logging_steps: 10
eval_steps: 100
save_steps: 200
```

### 3b. Launch on Lambda

Script: `scripts/launch_train.py`
- Provision: Lambda API → 1× A100 80GB spot, image=`pytorch:cuda12-2026`
- Startup script:
  ```bash
  #!/bin/bash
  set -e
  cd /workspace
  git clone https://github.com/tem-llm/tem-llm-build .
  pip install -r requirements.txt
  huggingface-cli login --token $HF_TOKEN
  wandb login $WANDB_KEY
  axolotl train configs/sft_v0.yaml
  axolotl push tem-llm/tem-rust-1.7b-v0
  shutdown -h now
  ```
- Lambda auto-shuts on instance halt → no idle charges
- Claude Code polls HF for checkpoint every 30 min via `ScheduleWakeup`

### 3c. Eval after training

```bash
python eval/run.py --model tem-llm/tem-rust-1.7b-v0 --eval all
python eval/aggregate.py
```

Append to `BASELINES.md` with v0 row.

---

## Stage 4 — Synthetic Generation (Phase 3)

### 4a. Teacher inference server

Provision separate A100 spot instance with vllm:
```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-Coder-Next \
  --quantization fp8 \
  --max-model-len 16384 \
  --port 8000
```

### 4b. Generation client

Script: `scripts/gen_synthetic.py`
- Reads `data/sources/post_cutoff_issues.jsonl` (collected fresh, post 2026-01)
- For each: send to teacher with agent loop prompt
- Get patch + reasoning
- Apply patch, run `cargo test`
- Keep only test-passing trajectories
- Output: `data/clean/synthetic_issues.jsonl`

Quality gate: if test-pass rate < 50%, abort and re-tune prompt.

### 4c. v1 training

Same as v0 but with `data/sft_v1.jsonl` (= v0 mix + synthetic).

---

## Stage 5 — GRPO (Phase 4, optional)

### 5a. Environment

Wrap 200 R2E-Gym-style Rust tasks. Each task is `(repo, base_sha, target_test)`.
Reward function:
```python
def reward(patch: str, task: dict) -> float:
    apply_patch(task.repo, task.base_sha, patch)
    result = run_cargo_test(task.repo, task.target_test)
    if result.target_pass and not result.regressions:
        return 1.0
    if result.target_pass and result.regressions:
        return 0.5
    if result.compiles:
        return 0.1
    return 0.0
```

### 5b. Unsloth GRPO config

`configs/grpo.yaml`:
```yaml
base_model: tem-llm/tem-rust-1.7b-v1
adapter: qlora
lora_r: 16
lora_alpha: 32

algorithm: grpo
num_rollouts: 8
kl_coef: 0.04
learning_rate: 5e-6
max_steps: 200
reward_fn: scripts/cargo_reward.py:reward

output_dir: ./outputs/tem-rust-v2
hub_model_id: tem-llm/tem-rust-1.7b-v2
```

Hard cap: 24 hrs wall time. If reward not improving by step 100, abort and ship v1.

---

## Stage 6 — Quantize & Package

### 6a. GGUF quantization

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make -j

# Merge LoRA into base
python ../scripts/merge_lora.py \
  --base Qwen/Qwen3-1.7B-Base \
  --lora outputs/tem-rust-v1 \
  --out merged/tem-rust-1.7b

# Convert to GGUF
python convert-hf-to-gguf.py merged/tem-rust-1.7b \
  --outfile gguf/tem-rust-1.7b-f16.gguf

# Quantize
./llama-quantize gguf/tem-rust-1.7b-f16.gguf gguf/tem-rust-1.7b-Q4_K_M.gguf Q4_K_M
./llama-quantize gguf/tem-rust-1.7b-f16.gguf gguf/tem-rust-1.7b-Q5_K_M.gguf Q5_K_M
./llama-quantize gguf/tem-rust-1.7b-f16.gguf gguf/tem-rust-1.7b-Q2_K.gguf Q2_K
```

### 6b. Mac inference verification

```bash
./llama-cli -m gguf/tem-rust-1.7b-Q4_K_M.gguf -p "fix this Rust code" -n 200
# Verify ≥ 30 tok/s output
```

### 6c. CLI tool (Rust crate)

Layout:
```
tem-rust-cli/
├── Cargo.toml
├── src/
│   ├── main.rs       # clap CLI dispatcher
│   ├── inference.rs  # llama.cpp wrapper via llama-cpp-2
│   ├── prompts.rs    # task templates (fix, test, review)
│   ├── cargo.rs      # cargo invoker for verification
│   └── repl.rs       # interactive mode
└── README.md
```

CLI surface:
```
tem-rust fix <file>           # fix compile errors
tem-rust test <file::fn>      # generate test
tem-rust review <diff>        # clippy-style review
tem-rust explain <error>      # explain rustc error
tem-rust chat                 # interactive REPL
```

Distribution:
- `cargo install tem-rust` → fetches CLI + auto-downloads GGUF on first run
- `brew install tem-rust` → tap with bottled binaries
- HuggingFace: weights + GGUF
- crates.io: CLI source
- GitHub: public repo with all of the above

---

## Stage 7 — Distribution

### 7a. HuggingFace release

- Repo: `tem-llm/tem-rust-1.7b`
- Files: safetensors, GGUF (3 quants), tokenizer, model card
- Model card: usage examples, eval results, training recipe link, citation

### 7b. crates.io publish

```bash
cd tem-rust-cli
cargo publish --token $CRATES_TOKEN
```

### 7c. Landing page

Static GitHub Pages from `tem-llm.github.io`:
- Hero: 30s demo gif
- Quickstart: `cargo install tem-rust && tem-rust fix src/main.rs`
- Benchmarks table (TemRust-* + comparison to baselines)
- Link to HF, crates.io, GitHub repo

### 7d. Launch posts

- r/rust thread (technical, with benchmarks)
- This Week in Rust submission
- HuggingFace blog post (recipe-focused)
- Hacker News Show HN
- Twitter/X thread

---

## Tool Reference

| Stage | Tool | Why |
|---|---|---|
| Crawling | PyGithub, gh CLI | Standard |
| AST | tree-sitter-rust, syn | Rust-native |
| Verifier | cargo, rustc, clippy | Ground truth |
| Training | Unsloth + Axolotl | 2026 single-GPU king |
| RL | Unsloth GRPO | Fits T4 |
| Teacher inference | vllm | Throughput |
| Quantization | llama.cpp | M-series native |
| CLI | clap, llama-cpp-2 | Rust-native |
| Eval | custom Python | Own the harness |
| Tracking | wandb (free tier) | Standard |
| Provisioning | Lambda CLI | Cheapest reliable |
| Storage | HuggingFace + Cloudflare R2 | Free / cheap |

---

## Sources

- [Unsloth Docs](https://unsloth.ai/docs)
- [Axolotl Docs](https://docs.axolotl.ai/)
- [Qwen3 launch](https://qwenlm.github.io/blog/qwen3/)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
- [DeepSeek-R1-Distill-Qwen-14B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B)
- [Qwen3-Coder-Next](https://qwen.ai/blog?id=qwen3-coder-next)
- [DeepSeekMath / GRPO](https://arxiv.org/abs/2402.03300)
- [R2E-Gym](https://arxiv.org/abs/2504.07164)
- [llama-cpp-2 Rust crate](https://crates.io/crates/llama-cpp-2)
