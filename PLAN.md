# PLAN — Tem-Rust-1.7B (Solo, $500, Autonomous)

**Locked 2026-05-05** after three pivots. This is the build plan, not a research plan. When earlier docs disagree, this wins.

---

## §0. Win Condition

Ship **Tem-Rust-1.7B**, a 1.7B Rust coding specialist. By end of project:

1. **TemRust-Issue ≥ 35%** (real GitHub Rust issues, post-cutoff, manually curated, `cargo test` verifier)
2. **TemRust-Borrow ≥ 60%** + **TemRust-Type ≥ 60%** + **TemRust-Clippy ≥ 50%** + **TemRust-Test ≥ 50%**
3. **Run at ≥ 30 tok/s on M3 Pro at int4** (Q4_K_M GGUF)
4. **Cleanly outperforms Qwen2.5-Coder-1.5B-Instruct** on TemRust-* by ≥ 10 pts on every sub-eval
5. **Within 5 pts of Qwen2.5-Coder-7B-Instruct** on at least 3 of 5 sub-evals (the "1.7B fights 7B" surprise)

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
| Compute budget | **$500 hard cap** |
| Headcount | 1 (Quan, hands-off) + Claude Code as autonomous executor |
| Calendar time | ~10 weeks |
| License | Apache-2.0 (weights + recipe + CLI) |
| Teacher | Qwen3-Coder-Next (open, MoE 3B-active, primary) OR DSR1-Distill-Qwen-14B (open, MIT, fallback) |
| GPU vendor | Lambda Labs spot A100 80GB ($1.49/hr) |

---

## §2. Architecture

| Component | Choice |
|---|---|
| Base | Qwen3-1.7B-Base (Apache-2.0) — fallback Qwen2.5-Coder-1.5B-Base |
| Adapter | QLoRA: 4-bit NF4 base + rank-16 / α-32 / dropout-0.05 LoRA |
| Targets | q/k/v/o + gate/up/down (full attention + MLP) |
| Optimizer | AdamW 8-bit |
| LR / schedule | 2e-4 / cosine, warmup 0.03 |
| Sequence length | 8K |
| Batch | per-device 1, grad-accum 32 (eff = 32) |
| Precision | bf16 |
| Output quant | int4 NF4 GGUF (Q4_K_M); also Q5_K_M and Q2_K |
| Inference (Mac) | llama.cpp / Ollama |
| Training framework | Unsloth (single-GPU king); Axolotl YAML for orchestration |
| RL framework (Phase 4) | Unsloth GRPO; TRL fallback |

---

## §3. Data Strategy

Five sources, all `cargo`-verifiable.

| Source | Target | Verifier |
|---|---|---|
| Real GitHub Rust issues (issue → fix-PR with added test) | 3,000 | `cargo test` |
| Synthetic compiler-error fixes | 2,000 | `cargo check` |
| Test generation pairs from well-tested crates | 1,500 | `cargo test` |
| Clippy idiomatic refactors | 1,000 | `cargo clippy -- -D warnings` |
| Phase-2 self-distillation on post-cutoff issues | 2,000 | `cargo test` |
| **Total target** | **~9,500** | |

After dedup + decontamination against eval suite: **~7-8K usable**.

Pipeline:
1. Local crawler pulls from top ~500 Rust repos (stars > 100, has tests, recently active)
2. Issue-PR matcher finds: failing-test-before, fix-PR, passing-test-after
3. For each match: extract `(issue_text, repo_state, diff, test_cmd)`
4. For corruption-style synthetic: programmatically introduce errors, ask teacher to fix, verify
5. For test-gen: extract `(fn_signature + body, #[test] block)` from existing crates
6. For clippy: run clippy on un-cleaned code, ask teacher to apply suggestion, verify
7. Decontaminate: every example checked against TemRust-* eval suite via exact + embedding match

---

## §4. Eval Suite (we own this)

| Sub-eval | Tasks | Verifier |
|---|---|---|
| TemRust-Borrow | 50 | `cargo check` |
| TemRust-Type | 50 | `cargo check` |
| TemRust-Test | 50 | `cargo test` |
| TemRust-Clippy | 50 | `cargo clippy -- -D warnings` |
| TemRust-Issue | 50 (real, post-cutoff) | repo-specific tests |
| **Total** | **250** | |

Hand-curated. Held back from training. Released publicly alongside the model. Becomes the de-facto Rust-LLM benchmark.

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

### Phase 4 — GRPO Mini-RL (Week 7–9, $50, OPTIONAL)
- Use 200 R2E-Gym-style Rust tasks (built from Phase 1 data)
- Unsloth GRPO with `cargo test` reward (binary +1/0)
- Curriculum: easy → hard
- Hard cap: 24 hrs ($36) on A100 + $5 eval = $41 worst case (under $50 ceiling)
- **If v1 already meets §0 win condition, SKIP this phase** and save the budget

**Exit criterion:** v2 (RL'd) beats v1 by ≥ 3 pts on TemRust-Issue, OR phase skipped if v1 met bar.

### Phase 5 — Quantize, Package, Ship (Week 9–10, $10)
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

## §7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Qwen3-1.7B-Base not released as bare base (only -Instruct or -Thinking) | Med | Med | Fallback to Qwen2.5-Coder-1.5B-Base verified Phase 0 |
| Data corpus < 5K after filter | Med | High | Backstop: synthetic-only training; widen Source 2-4 targets |
| Teacher quality insufficient for synthetic data | Med | Med | Try multiple teachers; quality gate ≥ 50% test-pass before bulk run |
| GRPO unstable at 1.7B | Med | Low | Skip Phase 4 if v1 hits bar; ship v1 |
| 1.7B too small for tool-use chains | Med | High | Phase 0 baselines tell us early; if base fails 5% on Issue, escalate to 3B |
| Cloud GPU price changes | Low | Low | Use vast.ai or RunPod fallback; rebudget if >2x change |
| Claude Code session limits break long runs | High | Low | Cloud jobs run unattended; we poll, not stream |
| User loses Lambda API credentials | Low | Med | Document recovery in AUTOMATION.md |
| Budget overrun | Med | High | Per-phase hard caps; >$50 single transaction needs auth |
| No-one cares about a small Rust model | Med | Med | Mitigate via demo quality + r/rust post + integration with TEMM1E |

---

## §8. Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-05-05 | Pivot 1: general → agentic coding | Strict canon thesis is benchmark-fit |
| 2026-05-05 | Pivot 2: 7B → 1.7B / $500 / solo | Owner's hard constraint |
| 2026-05-05 | Pivot 3: research → product | Owner wants something people use, not A/B |
| 2026-05-05 | Pivot 4: generic → Rust specialist | Niche uncontested; cargo = perfect verifier; aligns with TEMM1E |
| 2026-05-05 | Distribution: HF + crates.io + r/rust | Rust-native distribution channels |
| 2026-05-05 | Eval: build TemRust-* (250 tasks, cargo-verified) | Own the benchmark = own the moat |

---

## §9. Next Action

1. User authorises $500 budget + provides Lambda + HF + GitHub credentials
2. I provision cloud, run Phase 0 baselines, build eval harness
3. Phase 0 milestone report at end of Week 2 → user reviews → Phase 1 starts

**Status: awaiting user go-ahead.**
