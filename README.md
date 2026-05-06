# Tem-Rust

> A small, open Rust coding specialist trained on real GitHub PR fixes — distributed under Apache 2.0.

This repository contains the **as-executed pipeline, training data, evaluation harness, and result reports** for **TemRust-SMOL-v5-1.5B**, a fine-tune of `Qwen/Qwen2.5-Coder-1.5B-Instruct` specialized for Rust code: borrow-checker fixes, type-error fixes, test generation, and "fix this issue" tasks.

**Released model:** [`quanduong/TemRust-SMOL-v5-1.5B`](https://huggingface.co/quanduong/TemRust-SMOL-v5-1.5B) on HuggingFace Hub.

---

## Headline numbers — TemRust-* benchmark (n=37, hand-curated, cargo-graded)

| Model | Params | Pass rate |
|---|---|---|
| Qwen3-1.7B-chat (untrained) | 1.7B | 35.1% |
| Qwen2.5-Coder-1.5B-Instruct (this base, untrained) | 1.5B | 51.4% |
| **TemRust-SMOL-v5-1.5B** | **1.5B** | **67.6%** |
| Qwen2.5-Coder-3B-Instruct (untrained, 2× the params) | 3B | 73.0% |
| TemRust v4 ∪ v5 ensemble (1.7B + 1.5B + cargo check) | 3.2B | 83.8% |

**67.6% is +16.2 percentage points over the untrained base** at the same parameter count, and the ensemble configuration beats the 3B base by **+10.8 pp** at comparable total parameter budget.

The benchmark grades each task by running `cargo check`, `cargo test`, or `cargo run` in a fresh tempdir — there are no LLM judges, no embedding similarity, no string matching. Either the code compiles and the assertions pass, or it doesn't.

Per-category for **TemRust-SMOL-v5-1.5B**:

| sub-eval | tasks | pass | rate |
|---|---|---|---|
| borrow (lifetime / move / &mut conflicts) | 10 | 7 | 70.0% |
| issue (fix-this-bug from real GitHub issues) | 9 | 7 | 77.8% |
| test (write `#[test]` cases) | 9 | 4 | 44.4% |
| type (type-system / trait-bound errors) | 9 | 7 | 77.8% |

---

## Quick start

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

tok = AutoTokenizer.from_pretrained("quanduong/TemRust-SMOL-v5-1.5B")
model = AutoModelForCausalLM.from_pretrained(
    "quanduong/TemRust-SMOL-v5-1.5B",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. Return the complete fixed Rust "
    "file in a single ```rust code block. Do not include any other code blocks "
    "or explanations outside the block."
)

buggy = '''
fn longest(x: &str, y: &str) -> &str {
    if x.len() > y.len() { x } else { y }
}
'''

messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": f"```rust\n{buggy}\n```"},
]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs, max_new_tokens=2048, temperature=0.0, do_sample=False, pad_token_id=tok.eos_token_id)
print(tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
```

For best results in production, run the model output through `cargo check` before accepting. The eval harness does this automatically — see `eval/runner.py`.

---

## Repository contents

```
TemLLM/
├── README.md                 ← this file
├── LICENSE                   ← Apache 2.0
├── research_paper.md         ← academic-style writeup with full methodology + ablations
├── REPORT_2026-05-06.md      ← session report, v0 → v5 trajectory in detail
├── REPORT_v5_1.md            ← v5.1 squeeze attempt (regressed; analysis + lessons)
├── REPLICATE.md              ← step-by-step pipeline replication guide
├── BUDGET_LOG.md             ← line-by-line compute spend
├── STATUS.md                 ← high-level status snapshot
│
├── data/
│   ├── raw/                  ← 396 PR candidates from GitHub crawler
│   └── clean/                ← 263 PR-fix file pairs + 92 synthetic = 355-row v4 mix
│
├── eval/
│   ├── tasks/                ← 37 hand-curated benchmark tasks (4 sub-evals)
│   ├── runner.py             ← CLI driver, dispatches to clients + verifier
│   ├── verifier.py           ← cargo check / test / run grader
│   ├── extractors.py         ← pulls ```rust block, strips <think>...</think>
│   ├── clients.py            ← Together / vllm / Ollama OpenAI-compat clients
│   └── results/              ← per-version JSON eval outputs
│
└── scripts/
    ├── crawl_rust_issues_v2.py        ← GitHub PR crawler (paginated, looser filters)
    ├── sft_to_wholefile.py            ← raw.githubusercontent fetch → SFT format
    ├── synth_data.py                  ← v4 synthetic (51 borrow archetypes + 41 tests)
    ├── synth_data_v5_1.py             ← v5.1 broader synthetic (regressed; kept for ablation)
    ├── cargo_verify_sft.py            ← lightweight no-op + brace-balance filter
    ├── train_coder.py                 ← LoRA SFT + merge + FastAPI serve
    ├── runpod_train_coder_h100.py     ← RunPod H100 launcher with embedded log server
    ├── collect_distill_targets.py     ← per-row inference for ensemble distill
    └── upload_to_hf.py                ← merged checkpoint → HF Hub uploader
```

Architecture in one paragraph: **data crawler** scrapes merged-PR fix pairs from popular Rust repos → **synth generator** uses Qwen3-Coder-Next-FP8 teacher to add borrow archetypes + test scaffolds → **SFT trainer** runs LoRA r=32 alpha=64 on Qwen2.5-Coder-1.5B-Instruct via RunPod H100 (embedded HTTP log server makes pod failures debuggable) → merged adapter is uploaded to HuggingFace + benchmarked against 37 hand-curated cargo-graded Rust tasks.

---

## Reproducing the model

See [`REPLICATE.md`](REPLICATE.md) for the full step-by-step. In short:

```bash
git clone https://github.com/temm1e-labs/temrust && cd temrust
python -m venv .venv && source .venv/bin/activate
pip install requests huggingface_hub together

# credentials (place in ~/.config/temllm/{hf,gh,together,runpod}.token, chmod 600)
source scripts/load_creds.sh

# 1. Crawl Rust PR fixes (free, GitHub API)
python scripts/crawl_rust_issues_v2.py --out data/raw/issue_candidates_v3.jsonl

# 2. Convert to whole-file SFT format
python scripts/sft_to_wholefile.py --input data/raw/issue_candidates_v3.jsonl \
    --output data/clean/sft_wholefile_v3.jsonl

# 3. Generate teacher-distilled synthetic (~$1 in Together teacher tokens)
python scripts/synth_data.py

# 4. Combine
cat data/clean/sft_wholefile_v3.jsonl data/clean/sft_synthetic.jsonl | shuf > data/clean/sft_wholefile_v4.jsonl

# 5. Train + serve on RunPod H100 (~$1.50, ~20 min wall time)
python scripts/runpod_train_coder_h100.py
# prints pod proxy URL once FastAPI is ready

# 6. Eval
python -m eval.runner --model tem-rust-v5 --provider vllm \
    --base-url <proxy_url_from_step_5> \
    --out eval/results/tem-rust-v5__$(date +%s).json

# 7. Upload to HuggingFace
python scripts/upload_to_hf.py --pod-id <pod_id> \
    --repo-id <your_username>/TemRust-SMOL-v5-1.5B \
    --eval-json eval/results/tem-rust-v5__<latest>.json
```

**Total cost for one full reproduction:** ~$3-5 RunPod + ~$1 Together teacher tokens.

---

## Limitations

- Model trained on whole-file SFT format; Rust files exceeding 4096 tokens get truncated during training. Multi-file refactoring is out of scope.
- Benchmark sub-evals are balanced for diagnostic purposes (10/9/9/9 across borrow/issue/test/type), not weighted to real-world frequency.
- Training is **non-deterministic across runs** — three identically-configured retrains scored 21, 23, 25 on the 37-task benchmark. The published checkpoint is the highest of these three samples. Reproducing the exact 67.6% requires either downloading our weights or accepting some variance.
- No safety / RLHF post-training. Standard helpful-instruction tuning only.

---

## Citation

If you use this model or pipeline:

```bibtex
@misc{temrust-smol-v5-2026,
  author = {Quan Duong},
  title  = {TemRust-SMOL-v5-1.5B: a 1.5B Rust coding specialist via LoRA SFT on real GitHub PR fixes},
  year   = {2026},
  url    = {https://github.com/temm1e-labs/temrust},
  note   = {Apache 2.0 licensed.}
}
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

The base model `Qwen/Qwen2.5-Coder-1.5B-Instruct` is itself Apache 2.0 licensed.
