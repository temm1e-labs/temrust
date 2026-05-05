# OPEN QUESTIONS — Decided & Pending

Q1–Q5 answered 2026-05-05 after the agentic-coding pivot. Q6–Q10 still need decisions before Phase 0 is complete. See `PLAN.md` for the locked plan.

---

## ANSWERED

### Q1 — Which axis of "smart"? ✅ **Agentic coding capability per parameter**
Specifically: GitHub-issue → patch resolution. Verifiable via test pass. Not "general intelligence" — that's vapor at small scale and the field knows it.

### Q2 — Build new or beat existing? ✅ **Beat existing**
Win condition: 7B dense matches DeepSWE-Preview-32B on SWE-bench Verified, top-3 open at ≤7B on SWE-bench Pro.

### Q3 — Corpus definition? ✅ **Agent trajectory data, not "high-IQ canon"**
Mix: R2E-Gym (primary), SWE-Gym, Agent-FLAN, AceCoder, OpenHands traces, Llama-Nemotron-Post-Training agentic subset, Phase-2 synthetic from open teachers. The "top 1% literature" framing is dropped — agents need StackOverflow, error logs, and broken APIs, not Tolstoy.

### Q4 — Distillation source? ✅ **Open teachers at v0**
DeepSeek-V3.1, Qwen3-Coder-Next, or self-improving Phase-1 model. No Claude / GPT-5 unless an explicit ToS review clears it.

### Q5 — Base or scratch? ✅ **Post-train on existing strong base**
Candidates: Qwen2.5-Coder-7B-Base, DeepSeek-Coder-V3-7B, Qwen3-Coder dense 7B if/when released. Decision in Phase 0 after baseline evals.

---

## PENDING

### Q6 — Eval suite final composition?

Locked in `PLAN.md` §0 win condition:
- SWE-bench Verified (primary, but contaminated)
- SWE-bench Pro (contamination-resistant)
- SWE-bench-Live (rolling)
- τ-bench (tool use)
- Private holdout of 50–100 post-cutoff GitHub issues (release-gate metric)

**Open sub-question:** how do we source the private holdout? Manual curation is the safest answer; partial automation (filter for "issues with merged-fix PRs in last 30 days, repo with passing CI") is faster. **Decision needed: who builds it, and how big?**

### Q7 — Solo or collaborator?

The single largest project risk per `PLAN.md` §6 is silent data-pipeline bugs. A collaborator on data engineering (Phase 1–2) cuts this risk dramatically.

**Decision needed:** solo, or recruit one ML/data engineer? Where would they come from?

### Q8 — Compute budget commitment?

Plan calls for **$25K–65K** total over 6 months. State a number. Possible sources:
- Self-funded
- Anthropic / OpenAI / Cohere research-credit programs
- Lambda Labs Research Cloud credits
- AWS / GCP startup credits via existing entity
- Crowdfunding for an open-weights release

**Decision needed: budget envelope and source.**

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
