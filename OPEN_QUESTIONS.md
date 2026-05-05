# OPEN QUESTIONS — Decided & Pending

Q1–Q5 answered 2026-05-05 after the agentic-coding pivot. Q6–Q10 still need decisions before Phase 0 is complete. See `PLAN.md` for the locked plan.

---

## ANSWERED

### Q1 — Which axis of "smart"? ✅ **Agentic coding capability per parameter, at the 1B-class size**
Specifically: GitHub-issue → patch resolution at 1.7B params. Verifiable via test pass. The "1.7B beats 3B" surprise is the framing.

### Q2 — Build new or beat existing? ✅ **Beat existing at the 1B-class size**
Win condition: 1.7B dense beats Qwen2.5-Coder-3B-Instruct on SWE-bench Lite. (Pivoted from 7B/$25-65K plan to 1.7B/$500/solo on 2026-05-05.)

### Q3 — Corpus definition? ✅ **Agent trajectory data + 10–20% reasoning supplement (the canon-thesis ablation)**
- **Primary (80–90%):** R2E-Gym, AceCoder, OpenHands trajectories, Tulu-3 (filtered for tool use), Phase-2 synthetic from open teachers.
- **Reasoning supplement (10–20%):** MetaMathQA, OpenMathInstruct-2, algorithm derivations. **This is the salvaged piece of the original canon thesis** — not as the main corpus, but as a "reasoning stiffener" mixed into SFT. **Run with-vs-without ablation; this IS the originality lever.**
- **Dropped:** literature, philosophy, "top 1% canon." Doesn't help coding agents. Inherited via base-model pretraining anyway.

### Q4 — Distillation source? ✅ **Open teachers at v0**
DeepSeek-V3.1, Qwen3-Coder-Next, or self-improving Phase-1 model. No Claude / GPT-5 unless an explicit ToS review clears it.

### Q5 — Base or scratch? ✅ **Post-train on Qwen3-1.7B-Base**
Primary: Qwen3-1.7B-Base (Mar 2026 release, matches Qwen2.5-3B-Base on benchmarks, Apache-2.0). Fallback: Qwen2.5-Coder-1.5B-Base. Decision finalised after Phase 0 baseline runs. Stretch (post-success): 0.6B distillation.

---

## PENDING (Q9, Q10) — Q6, Q7, Q8 answered 2026-05-05

### Q6 — Eval suite final composition? ✅

Locked in `PLAN.md` §0:
- **Primary:** SWE-bench Lite (vs Qwen2.5-Coder-3B-Instruct as the bar)
- SWE-bench Verified ≥ 20% (sample 100 issues if full 500 is too expensive)
- **Private holdout: 30–50 post-cutoff GitHub issues — release-gate metric, manually curated by Quan**
- τ-bench (tool use)
- Inference: ≥ 20 tok/s on M3 Pro at int4

### Q7 — Solo or collaborator? ✅ **Solo**
Quan only. No collaborator at v0. Mitigation for the data-pipeline-bug risk: daily distribution sanity-checks, commit datasets to git LFS, weekly self-review of pipeline diffs.

### Q8 — Compute budget? ✅ **$500 hard cap**
Self-funded. Phase-by-phase sub-caps in `PLAN.md` §6. Spend rules:
- Lambda Labs spot A100 ($1.50/hr) = default rental
- Kaggle T4 (30 hrs/week free) and Colab T4 = free runs
- Track every USD in `BUDGET_LOG.md` (to be created Phase 0)
- Weekly burn review; if any phase exceeds its ceiling, stop and re-plan

### Q9 — Open or closed?

Options:
- (a) Apache-2.0 weights + recipe + technical report (max impact, no commercial moat)
- (b) Weights closed, recipe published (some moat, less community pickup)
- (c) Closed end-to-end (full moat, high risk it never pays back)

**Recommendation:** (a). The Phi/DeepSeek/Qwen lesson is that visibility >> moat for a project of this size. But this is a strategic decision, not a default.

**Open sub-question:** licence of training data. R2E-Gym is Apache, SWE-Gym is permissive, Llama-Nemotron is mixed — must check before any release.

### Q10 — Done criterion?

`PLAN.md` §0 has the metric version. The strategic version is still open:
- (a) Hit win condition → public release → technical report → done.
- (b) Hit win condition → public release → keep iterating to push frontier further.
- (c) Build into a product (CLI tool, IDE extension, hosted endpoint).

**Decision needed:** what does "shipped" mean for this project?

---

## Connection to wider Tem / TEMM1E?

Still open. Possible connections:
- TemLLM as the LLM that powers the agentic core in TEMM1E (Rust runtime calls a local TemLLM for code-related actions)
- TemLLM and TEMM1E are intentionally separate projects with shared branding only
- TemLLM as a research playground; TEMM1E uses frontier APIs in production

**Decision needed.** If TemLLM is meant to power TEMM1E locally, the deployment surface (M-series Mac, no cloud GPU) becomes a hard constraint and may push the param target down to 4B or even lower. This single decision can change Phase 4.
