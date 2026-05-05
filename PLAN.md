# PLAN — Tem-Rust-1.7B (Solo, $200, Autonomous, Zero-Risk)

**Locked 2026-05-05** (revised same day for zero-risk + $200 budget). This is the build plan, not a research plan. When earlier docs disagree, this wins.

---

## §0. Win Condition

Ship **Tem-Rust-1.7B**, a 1.7B Rust coding specialist. By end of project:

1. **TemRust-Issue ≥ 25%** (real GitHub Rust issues, post-cutoff, manually curated, `cargo test` verifier) — calibrated against Strand-Rust-Coder-14B's 43-48% on Rust benchmarks (60% relative at 12% of params is honest)
2. **TemRust-Borrow ≥ 60%** + **TemRust-Type ≥ 60%** + **TemRust-Test ≥ 50%** (Clippy deferred to v1.1)
3. **Run at ≥ 30 tok/s on M3 Pro at int4** (Q4_K_M GGUF)
4. **Cleanly outperforms Qwen2.5-Coder-1.5B-Instruct** on TemRust-* by ≥ 10 pts on every sub-eval
5. **MultiPL-E Rust ≥ Qwen2.5-Coder-3B-Instruct's score** (the "1.7B beats 3B" public-benchmark headline)
6. **RustEvo² + Aider Polyglot Rust slice** scored alongside (credibility, not gating)

**Stretch:** within 5 pts of Qwen2.5-Coder-7B-Instruct on at least 3 of 5 sub-evals; within 10 pts of Strand-Rust-Coder-14B on Rust-specific tasks at 12% of its params.

**Shipped artifacts:**
- HuggingFace: `tem-llm/tem-rust-1.7b` (Apache-2.0 weights + GGUF quants)
- crates.io: `tem-rust` CLI (`cargo install tem-rust`)
- GitHub: project repo with model card, training recipe, eval harness
- Landing: `tem-rust.dev` or GitHub Pages with 30s demo gif
- r/rust launch post + technical blog post

**Out of scope:** general chat, non-Rust languages, vision, voice, training data > 10K examples, multi-language eval.

---

## §1. Constraints

| Constraint | Value |
|---|---|
| Param size | 1.7B dense (Qwen3-1.7B-Base) |
| Compute budget | **$200 hard cap** ($35 committed, $165 reserve = 82% margin) |
| Headcount | 1 (Quan, hands-off) + Claude Code as autonomous executor |
| Calendar time | ~6-8 weeks |
| License | Apache-2.0 (weights + recipe + CLI) |
| Teacher | Qwen3-Coder-Next (open, MoE 3B-active) via **Together AI hosted inference** ($0.40/Mtok) |
| GPU vendor | **RunPod A100 PCIe 40GB Community** ($0.60/hr) — 60% cheaper than prior Lambda quote |
| Risk posture | **Zero-risk: GRPO Phase 4 SKIPPED** (RL at 1.7B is the highest single failure mode) |

---

## §2. Architecture (best available May 2026)

| Component | Choice | Why best |
|---|---|---|
| Base (primary) | **Qwen3-1.7B-Base** (Apache-2.0, [HF](https://huggingface.co/Qwen/Qwen3-1.7B-Base)) | Strongest open 1.7B base; matches Qwen2.5-3B-Base on benchmarks |
| Base (fallback A) | Qwen3.5-2B-Base (Mar 2026 release) | Newer arch, slightly larger; Phase 0 baselines pick winner |
| Base (fallback B) | Qwen2.5-Coder-1.5B-Base | Already code-tuned; safety net |
| Adapter | QLoRA: 4-bit NF4 base + rank-16 / α-32 / dropout-0.05 LoRA | 2026 default; proven |
| Targets | q/k/v/o + gate/up/down | Full attention + MLP reach |
| Optimizer | AdamW 8-bit | Memory-efficient |
| LR / schedule | 2e-4 / cosine, warmup 0.03 | Unsloth defaults |
| Sequence length | **4K** (was 8K) | Most Rust files fit; 30% faster training |
| Batch | per-device 1, grad-accum 32 (eff = 32) | Standard |
| Precision | bf16 | Standard |
| Output quant | int4 NF4 GGUF (Q4_K_M); also Q5_K_M and Q2_K | M-series Mac native |
| Inference (Mac) | llama.cpp / Ollama | Standard |
| Training framework | **Unsloth + Axolotl YAML** | Single-GPU king (2-5× faster, 80% less VRAM) |
| Teacher | **Qwen3-Coder-Next (80B/3B-active MoE)** via Together AI | Best open coding teacher; hosted = no self-host cost |
| Compute provider | **RunPod A100 40GB Community** ($0.60/hr) | Cheapest reliable A100 in 2026 |

---

## §3. Data Strategy

Mix existing high-quality datasets with our cargo-verified sources.

| Source | Target | Type | Why |
|---|---|---|---|
| **Fortytwo-Network/Strandset-Rust-v1** | sample 30K of 191K | external | Strand's open-released training set; 15 task categories, peer-ranked. Saves us most of Phase 1 work. |
| The Stack v2 (Rust subset, permissive-licensed) | 5K filtered | external | Pretraining-grade Rust source code; for code-style priors |
| Real GitHub Rust issues (issue → fix-PR with added test) | 2,000 | ours | `cargo test` verified |
| Synthetic compiler-error fixes | 1,500 | ours | `cargo check` verified |
| Test generation pairs from well-tested crates | 1,000 | ours | `cargo test` verified |
| Clippy idiomatic refactors | 500 | ours | `cargo clippy -- -D warnings` verified |
| **Total post-dedup target** | **~25-35K** | | After dedup + decontamination |

**Key change:** instead of building 9.5K from scratch, we **start from the Strandset (proven) and layer our cargo-verified additions on top**. This dramatically reduces Phase 1 work and time. If Strandset is unsuitable on inspection, fall back to the original 5-source plan.

**Edit format (CRITICAL for small models):** structure-aware function-block diffs via tree-sitter-rust, NOT raw search/replace, NOT full-file rewrite. Per [Diff-XYZ](https://arxiv.org/html/2510.12487v1) and [AdaEdit](https://arxiv.org/html/2604.27296), this is worth +8-10 pts at 1.7B.

Pipeline:
1. Local crawler pulls from top ~500 Rust repos (stars > 100, has tests, recently active)
2. Issue-PR matcher finds: failing-test-before, fix-PR, passing-test-after
3. For each match: extract `(issue_text, repo_state, diff, test_cmd)`
4. For corruption-style synthetic: programmatically introduce errors, ask teacher to fix, verify
5. For test-gen: extract `(fn_signature + body, #[test] block)` from existing crates
6. For clippy: run clippy on un-cleaned code, ask teacher to apply suggestion, verify
7. Decontaminate: every example checked against TemRust-* eval suite via exact + embedding match

---

## §4. Eval Suite

**Owned (the moat):**

| Sub-eval | Tasks | Verifier |
|---|---|---|
| TemRust-Borrow | 50 | `cargo check` |
| TemRust-Type | 50 | `cargo check` |
| TemRust-Test | 50 | `cargo test` |
| TemRust-Issue | 50 (real, post-cutoff) | repo-specific tests |
| **Owned total** | **200** | |

Hand-curated. Held back from training. Released publicly alongside the model.

**Standard public benchmarks (run for credibility, not gating):**

| Benchmark | Source | Why |
|---|---|---|
| MultiPL-E Rust | [nuprl/MultiPL-E](https://github.com/nuprl/MultiPL-E) | HumanEval extended to Rust; the standard polyglot eval |
| RustEvo² | [SYSUSELab/RustEvo](https://github.com/SYSUSELab/RustEvo) | 588 Rust API evolution tasks (Rust 1.71→1.84) |
| Aider Polyglot Rust slice | [aider.chat/leaderboards](https://aider.chat/docs/leaderboards/) | ~37 Rust Exercism exercises |

These cost ~$5 total to run on our model; published on launch alongside TemRust-*.

---

## §5. Pipeline — 6 Phases

### Phase 0 — Foundations (Week 1–2, $20)
- Provision Lambda Labs (user one-time setup)
- Build local Mac dev environment: Unsloth, Axolotl, llama.cpp, vllm
- Build eval harness: `cargo`-verifier wrappers, scoring script, results dashboard
- Run baselines on TemRust-Issue + TemRust-Borrow:
  - Qwen3-1.7B-Base, Qwen3-1.7B-Instruct
  - Qwen2.5-Coder-1.5B-Base, -1.5B-Instruct
  - Qwen2.5-Coder-3B-Instruct
  - Qwen2.5-Coder-7B-Instruct
  - DSR1-Distill-Qwen-1.5B
- Lock primary base model based on baselines
- Eval dashboard live at end of phase

**Exit criterion:** all 250 eval tasks runnable; baseline scores recorded; primary base locked.

### Phase 1 — Data Collection (Week 2–4, $0)
- Crawl GitHub via API (free tier sufficient)
- Build issue-PR matcher
- Generate sources 1, 3, 4 (real issues, test pairs, clippy fixes)
- Defer source 2 (synthetic compiler errors) until Phase 3 since it needs teacher
- Decontamination pass against full eval suite
- Output: `data/sft_v0.jsonl` with ~5,500 examples

**Exit criterion:** ≥ 5K verified examples; decontamination report shows zero overlap with eval.

### Phase 2 — SFT v0 (Week 4–5, $30)
- Hyperparameter sweep: 3 runs varying LR, rank, mix
- Train Qwen3-1.7B-Base on `sft_v0.jsonl` with Unsloth QLoRA
- Eval after each run on TemRust-* suite
- Pick best checkpoint as `tem-rust-v0`
- Smoke test: int4 quant + run on M3 Pro

**Exit criterion:** v0 beats Qwen2.5-Coder-1.5B-Instruct on TemRust-Borrow + TemRust-Type by ≥ 5 pts.

### Phase 3 — Synthetic + SFT v1 (Week 5–7, $45)
- Provision teacher (Qwen3-Coder-Next or DSR1-Distill-Qwen-14B) on rented A100
- Generate Source 2 (synthetic compiler errors): ~2K examples
- Generate Source 5 (self-distillation on post-cutoff issues): ~2K examples
- Verify all via `cargo check` / `cargo test`
- Build `data/sft_v1.jsonl` = sft_v0 + new synthetic
- Train v1 with same setup
- Eval

**Exit criterion:** v1 beats v0 by ≥ 5 pts on TemRust-Issue.

### Phase 4 — SKIPPED (zero-risk decision)
GRPO at 1.7B is the highest-risk step in the pipeline (literature: convergence at <3B is uncharted). Skipped entirely in the zero-risk plan. If v1 dramatically misses the §0 bar AND reserve budget is healthy, can be re-added by user authorisation.

### Phase 5 — Quantize, Package, Ship (Week 7–8, $5)
- Quantize best checkpoint to GGUF: Q4_K_M (default), Q5_K_M (high), Q2_K (mobile)
- Verify ≥ 30 tok/s on M3 Pro at Q4_K_M
- Build CLI tool `tem-rust` in Rust:
  - `tem-rust fix <file>` — fix compile errors
  - `tem-rust test <file::fn>` — generate test
  - `tem-rust review <diff>` — clippy-style review
  - `tem-rust chat` — interactive REPL
- Wraps llama.cpp via `llama-cpp-2` Rust bindings
- Build landing page (GitHub Pages or `tem-rust.dev`)
- Record 30s demo gif
- Write technical blog post + r/rust launch post
- Push: HuggingFace weights + GGUF, crates.io CLI, GitHub repo public

**Exit criterion:** all artifacts public; CLI installable via `cargo install tem-rust`.

---

## §6. Automation Model

Claude Code is the executor. See `AUTOMATION.md` for the protocol.

**One-time setup (user, ≤ 30 min):** Lambda API key, HF write token, GitHub PAT, $500 budget authorisation.

**Per-week (user, ≤ 15 min):** open new session, say "continue Tem-Rust", review milestone if at phase boundary, approve any single transaction > $50.

**Continuous (Claude Code):** everything else — provisioning, training, eval, packaging, distribution.

---

## §7. Competitive Landscape (May 2026)

| Model | Params | Score | License | Position |
|---|---|---|---|---|
| Strand-Rust-Coder-14B-v1 | 14B | 43-48% Rust bench | Apache-2.0 | **Server-class Rust specialist** (Fortytwo Network) |
| Tessa-Rust-T1-7B | 7B | unclear, basic completion | varies | Earlier 7B attempt |
| Qwen3-Coder-Next | 80B/3B-active MoE | top open agentic | Apache-2.0 | General coder, MoE architecture |
| GPT-5.1 / Claude / Gemini 3 | frontier | 88% Aider Polyglot | closed | Strong Rust but expensive at scale |
| **Tem-Rust-1.7B** (us) | **1.7B** | **target ≥ 25% Rust bench** | **Apache-2.0** | **The on-device Rust specialist** |

The ≤ 2B Rust specialist niche is empty. Strand and Tessa serve different deployment targets (server-class). Our positioning: *"What Strand does at 14B server-class, Tem does at 1.7B on your laptop, offline, free."*

## §8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Strandset-Rust-v1 quality unsuitable on inspection | Low | Med | Fallback: original 5-source plan; cost negligible |
| Qwen3-1.7B-Base mismatch with code tasks | Low | Med | Phase 0 also baselines Qwen3.5-2B-Base + Qwen2.5-Coder-1.5B-Base |
| Edit format choice wrong for our model | Med | Med | Phase 2 ablates 2 formats: function-block diff vs unified diff |
| Teacher quality insufficient | Med | Med | Quality gate ≥ 50% test-pass before bulk run; switch to DSR1-Distill-14B |
| 1.7B too small for tool-use chains | Med | High | Phase 0 baselines tell us early; if base fails 5% on Issue, escalate to Qwen3.5-2B |
| Frontier model adoption kills market | Low | Med | Local + free + private + sub-second is the moat — frontier costs $$$ at scale |
| Strand ships 1.5B variant during our run | Low-Med | High | Time-box 8 weeks; first-mover; integrate into TEMM1E for distribution |
| Cloud GPU price changes | Low | Low | Use vast.ai fallback; rebudget if >2× change |
| Claude Code session limits break long runs | High | Low | Cloud jobs run unattended; we poll, not stream |
| Budget overrun | Med | High | Per-phase hard caps; >$30 single transaction needs auth |
| No-one downloads | Med | Med | Demo + r/rust + benchmark release + TEMM1E integration as distribution channels |

---

## §9. Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-05-05 | Pivot 1: general → agentic coding | Strict canon thesis is benchmark-fit |
| 2026-05-05 | Pivot 2: 7B → 1.7B / $500 / solo | Owner's hard constraint |
| 2026-05-05 | Pivot 3: research → product | Owner wants something people use, not A/B |
| 2026-05-05 | Pivot 4: generic → Rust specialist | Niche uncontested; cargo = perfect verifier; aligns with TEMM1E |
| 2026-05-05 | Distribution: HF + crates.io + r/rust | Rust-native distribution channels |
| 2026-05-05 | Eval: build TemRust-* (200 tasks, cargo-verified) + run MultiPL-E + RustEvo² + Aider Polyglot Rust | Own the moat + credibility |
| 2026-05-05 | **Pivot 5: $500 → $200 zero-risk** | User-set tighter budget; risk reduction priority |
| 2026-05-05 | Skip Phase 4 (GRPO) | Highest single failure mode at 1.7B |
| 2026-05-05 | Switch to RunPod A100 40GB ($0.60/hr) from Lambda ($1.49/hr) | 60% cost reduction; sufficient VRAM |
| 2026-05-05 | Teacher: Qwen3-Coder-Next via Together AI hosted | Best open coding teacher; per-token pricing |
| 2026-05-05 | Reduce seq length to 4K | Most Rust files fit; ~30% faster training |
| 2026-05-05 | **Use Fortytwo Strandset-Rust-v1 as primary data source** (191K open-released) | Proven recipe from Strand-Rust-Coder-14B; saves Phase 1 work |
| 2026-05-05 | **Edit format: structure-aware function-block diffs** via tree-sitter-rust | Critical for small models per Diff-XYZ / AdaEdit; worth +8-10 pts |
| 2026-05-05 | Position: "what Strand does at 14B server, Tem does at 1.7B on-device" | Strand-Rust-Coder-14B exists; 7B Tessa exists; ≤2B niche still uncontested |

---

## §10. Next Action

1. User authorises **$200** budget + provides RunPod + HF + GitHub credentials
2. I provision RunPod A100 40GB, run Phase 0 baselines on Qwen3-1.7B-Base + Qwen3.5-2B-Base + Qwen2.5-Coder-1.5B-Base, build eval harness
3. Phase 0 milestone report at end of Week 1-2 → user reviews → Phase 1 starts

**Status: awaiting user go-ahead.**
