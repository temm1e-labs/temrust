# PLAN — Best Small Open Coding Agent For Its Size

**Target locked 2026-05-05.** This document is the authoritative project plan. When earlier docs (`THEORY.md`, `FEASIBILITY.md`) disagree with this one, this one wins.

---

## §0. Win Condition (the precise version)

A **7B dense post-trained model** that, by end of project, satisfies **all** of:

1. **SWE-bench Verified ≥ 51%** — matches DeepSWE-Preview-32B at 7B (4.5× param efficiency)
2. **SWE-bench Pro ≥ 35%** — top-3 open dense model at ≤7B scale
3. **SWE-bench-Live ≥ 30%** — proves we generalize beyond contamination
4. **Private holdout (50–100 fresh post-cutoff GitHub issues) ≥ 40%** — proves we generalize beyond eval contamination of any kind
5. **τ-bench (tool use) ≥ 50%** — tool-call discipline, not just code patches

**Stretch:** distill 7B → **4B** retaining ≥ 80% of 7B SWE-bench Verified score. Deploy as on-device coding agent.

**Out of scope:** general LMSys Arena performance, world knowledge, multilingual chat, vision, voice. We do **one thing**: resolve real GitHub issues.

---

## §1. Constraints

| Constraint | Value |
|---|---|
| Param size (primary) | 7B dense |
| Param size (stretch) | 4B dense |
| Compute budget | **$25K–65K** total |
| Calendar time | 6 months single-builder; 4 months with 1 collaborator |
| Base model | Open-licence, post-trained on top of (Qwen2.5-Coder-7B-Base, DeepSeek-Coder-V3-7B, or Qwen3-Coder dense 7B if/when released) |
| Teacher (distillation) | Open only at v0: DeepSeek-V3.1, Qwen3-Coder-Next. Closed (Claude / GPT-5) only after explicit ToS review |
| License (output) | Apache-2.0 weights + recipe (decision pending — see OPEN_QUESTIONS Q9) |

---

## §2. The Recipe (5 phases)

### Phase 0 — Foundations (Weeks 1–3)

**Goal:** know exactly what we're beating, and have the eval infra to prove a beat.

- Stand up eval harness:
  - SWE-bench Verified ([swebench.com/verified.html](https://www.swebench.com/verified.html))
  - SWE-bench Pro ([morphllm.com/swe-bench-pro](https://www.morphllm.com/swe-bench-pro))
  - SWE-bench-Live ([swe-bench-live.github.io](https://swe-bench-live.github.io/))
  - SWE-rebench ([swe-rebench.com](https://swe-rebench.com/))
  - τ-bench (tool use)
  - **Private holdout: 50–100 fresh GitHub issues** (post-base-model-cutoff) with passing test suites
- Run baselines on full eval suite:
  - Qwen2.5-Coder-7B-Instruct
  - Qwen3-Coder-Next (3B-active MoE)
  - DeepSeek-Coder-V3-7B
  - DeepSWE-Preview (32B)
- Lock GPU access: 8×H100 reservation on Lambda / RunPod / Together
- Pick base model based on eval baselines + licence clarity
- Build dataset deduplication tooling: never train on a sample that overlaps any eval

**Exit criterion:** every benchmark runs end-to-end on at least one baseline. Numbers are reproducible. Private holdout exists.

**Cost: $1–3K. Compute: ~500 GPU-hours.**

### Phase 1 — SFT on existing public trajectory data (Weeks 4–7)

**Goal:** see how far open data alone moves the base model.

Datasets:
| Dataset | Tokens / Items | URL |
|---|---|---|
| **R2E-Gym** | 8.1K problems, 13 repos, executable envs | https://github.com/R2E-Gym/R2E-Gym |
| SWE-Gym | ~2K problems | https://github.com/SWE-Gym/SWE-Gym |
| Agent-FLAN | tool-use SFT mix | HF |
| AceCoder / AceCode-89K | 89K coding traces | HF |
| OpenHands trajectories | crowdsourced agent runs | HF |
| Llama-Nemotron-Post-Training (agentic subset) | filtered from 30M | https://huggingface.co/datasets/nvidia/Llama-Nemotron-Post-Training-Dataset-v1 |
| Tulu-3-SFT-Mixture (filtered for tool use) | ~939K | https://huggingface.co/datasets/allenai/tulu-3-sft-mixture |

Pipeline:
1. Pull all sources, schema-normalise to `{system, messages, tools, env_state}`
2. **Decontamination pass** — n-gram + embedding match against every eval set; drop any overlap
3. Filter trajectories: keep only those whose final patch passed unit tests
4. Mix per domain quotas (R2E-Gym 50%, SWE-Gym 20%, others 30%) — exact weights tunable
5. SFT 1–3 epochs, AdamW, packed sequences, 32K context
6. Eval after every epoch on full suite

**Exit criterion:** ≥ +5 points on SWE-bench Verified vs the chosen base.

**Cost: $3–8K. Compute: ~1,500 GPU-hours.**

### Phase 2 — Synthetic trajectory generation (Weeks 8–12)

**Goal:** generate tens of thousands of verified, post-cutoff trajectories the open SFT corpus doesn't have.

Pipeline:
1. Curate ~5K real GitHub issues from post-cutoff date in active repos (Python/TS/Rust/Go), with passing existing test suites
2. Wrap each in an R2E-Gym-style executable env (SWE-Playground recipe — https://arxiv.org/html/2512.12216)
3. Run an agent loop with the chosen open teacher (DeepSeek-V3.1, Qwen3-Coder-Next, or self-improving Phase 1 model)
4. Keep ONLY trajectories whose final patch passes all originally-passing tests AND doesn't break any other test
5. Annotate each with: difficulty (teacher-rated), tools used, # of turns, error-recovery events
6. SFT round 2 on union of (Phase 1 mix + new synthetic), with new synthetic upweighted

**Risk gate:** if any closed teacher (Claude, GPT-5) is considered, **explicit ToS review must happen before the first API call**. Default: open teachers only.

**Exit criterion:** ≥ +5 more points on SWE-bench Verified, AND ≥ +3 on private holdout.

**Cost: $5–15K (teacher inference dominates). Compute: ~2,000 GPU-hours of training + teacher API spend.**

### Phase 3 — RL on verifiable rewards (Weeks 13–22)

**Goal:** push from "good imitation of teacher" to "actually solves problems."

Setup:
- Environment: R2E-Gym 4,500-task RL set + Phase 2 synthetic envs
- Algorithm: **GRPO** (DeepSeekMath / DeepSeek-R1) with test-pass reward, optionally PPO if GRPO unstable at our scale
- Reward shaping:
  - Primary: all repo tests pass (sparse, ±1)
  - Shaping: code parses (+0.05), code runs without exception (+0.05), no regressions on other tests (+0.1), reasonable patch size (-penalty if > 200 LOC)
  - Optional: process reward model trained on step-quality from Phase 2 traces
- Curriculum: easy → hard, by teacher-rated difficulty from Phase 2
- Frame budget: 9,200 GPU-hours = DeepSWE's full run. Our target: 2,000–4,000 GPU-hours starting from a stronger SFT base.
- Tooling: OpenRLHF, verl, or SkyRL-Agent ([arxiv 2511.16108](https://arxiv.org/html/2511.16108))

**Exit criterion:** SWE-bench Verified ≥ 51% (DeepSWE-32B parity at 7B). If not hit by Week 22, freeze and ship the SFT-only model.

**Cost: $10–30K. Compute: 2,000–4,000 GPU-hours.**

### Phase 4 — Inference scaling, 4B distillation, ship (Weeks 23–28)

- Implement **R2E-Gym hybrid verifier** at inference: execution-based + execution-free verifiers, weighted, n=8 rollouts → best-of-n. This typically buys 5–10 points on SWE-bench at inference time.
- **4B distillation:** use Phase 3 7B as teacher; rejection-sample trajectories from R2E-Gym; SFT a Qwen-2.5-Coder-3B-base (or 4B variant) on filtered traces
- Final eval pass on **everything**: SWE-bench Verified, Pro, Live, Multilingual, τ-bench, private holdout, BigCodeBench, LiveCodeBench
- **Decide:** if win condition met, public release with weights + recipe + technical report. If not met, ship the technical report regardless — negative results are still results.

**Cost: $3–8K. Compute: ~1,000 GPU-hours.**

---

## §3. Edges (where we win against bigger teams)

We are not going to outspend Alibaba or Together AI. Our edges:

1. **Narrowness.** We are training one task: GitHub-issue → patch. Qwen3-Coder-Next is a generalist coder agent — we trade their breadth for depth on our axis.
2. **Stronger teachers than the labs had access to.** Qwen3-Coder-Next was trained against ~late-2025 frontier teachers; we use 2026-vintage teachers (Claude Opus 4.7 / DeepSeek-V3.1 / Qwen3-Coder-Next itself) in Phase 2.
3. **Post-cutoff data.** Our private holdout and Phase 2 synthetic come from issues none of the bases have seen — this isn't moat-as-cheating, it's moat-as-recency.
4. **Hybrid verification at inference.** R2E-Gym's hybrid-verifier paper shows large gains; not all teams have implemented it. We make it a first-class part of the recipe.
5. **Faster iteration on data composition.** A small team can do six data-mix experiments to a big team's one. The Phi/DeepSeek lesson is that data composition is the open lever — we exploit that.

What is **not** an edge: novel architecture, novel optimizer, novel scaling law. Those are PhD projects, not 6-month builds.

---

## §4. Tooling Stack

| Layer | Choice | Backup |
|---|---|---|
| Base models | HuggingFace Hub | — |
| Tokenization | reuse base tokenizer | — |
| SFT | Axolotl + Unsloth | TRL |
| RL | OpenRLHF + verl | TRL with GRPO impl |
| Multi-turn agent RL | SkyRL-Agent | custom on OpenRLHF |
| Inference | sglang | vllm |
| Eval | SWE-bench official harness, lm-evaluation-harness | bigcode-eval-harness |
| Env | R2E-Gym, SWE-Gym, SWE-Playground | custom Docker |
| Experiment tracking | Weights & Biases | mlflow |
| Compute | Lambda Labs / RunPod (spot) for SFT, Together for reliable RL | Coreweave for big runs |
| Storage | local NVMe + cheap S3 (Cloudflare R2) for datasets | — |

---

## §5. Datasets (everything we'll touch)

**Training:**
- R2E-Gym (8.1K problems, executable) — primary
- SWE-Gym, SWE-Playground, AceCoder, Agent-FLAN
- Llama-Nemotron-Post-Training (agentic subset)
- Tulu-3 (filtered)
- Phase 2 synthetic: ~50K–200K verified trajectories from open teachers

**Evaluation (decontaminated against training):**
- SWE-bench Verified (500 issues)
- SWE-bench Pro (contamination-resistant successor)
- SWE-bench-Live (rolling)
- SWE-bench Multilingual
- τ-bench (tool use)
- Private holdout (post-cutoff issues, sourced manually)

**Decontamination:** every training sample is checked against every eval set via (a) exact issue-ID match, (b) repo-level match, (c) embedding-similarity threshold. **No exceptions.**

---

## §6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Base model lacks clean licence | Med | High | Pre-flight licence audit; have Qwen2.5-Coder + DeepSeek-Coder both validated before Phase 0 closes |
| Teacher ToS forbids training competitors | High (closed) / Low (open) | High | Open teachers only by default; explicit legal review before any closed-teacher use |
| Eval contamination inflates scores | Very High | Critical | Private holdout is the only metric that gets a release-decision vote |
| RL training instability | High | High | Cheap PPO baseline before GRPO; cap per-phase compute; freeze SFT if RL fails |
| Frontier ships a 7B that beats us during our run | Med-High | High | Time-box phases; ship SFT-only model by Week 12 if signs of being lapped |
| Compute creep | Very High | High | Hard per-phase caps; if exceeded, stop, eval, and re-plan |
| Single-builder data bugs | High | Med | Pair-review every data-pipeline diff; sanity-check sample distributions weekly |
| 7B dense Qwen3-Coder base never ships | Med | Med | Fallback to Qwen2.5-Coder-7B-Base or DeepSeek-Coder-V3-7B confirmed in Phase 0 |

---

## §7. Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-05-05 | Pivot from "general intelligence per param" to "agentic coding capability per param" | Strict-form thesis (small + curated > all) is benchmark-fit, not utility. Agentic-coding is narrow, measurable, and has a real win condition. |
| 2026-05-05 | Target 7B dense, not 4B or 14B | 7B = single-GPU consumer hardware after light quant; cleanest leaderboard lane; 4B fights pre-tuned giants like Qwen3-4B; 14B exits "small" framing |
| 2026-05-05 | Beat DeepSWE-32B parity, not Qwen3-Coder-Next | DeepSWE is a fully open dense recipe with a known compute cost; Qwen3-Coder-Next is a closed-recipe MoE with Alibaba's full cluster behind it |
| 2026-05-05 | Private holdout is the release-gate metric | All public SWE-benches are partially contaminated; we cannot trust them for a SOTA claim |
| 2026-05-05 | Open teachers only at v0 | ToS risk + reproducibility |

Future decisions go here, dated.

---

## §8. Next Action (this week)

1. Confirm the win condition above (user signs off / pushes back).
2. Stand up Phase 0 eval harness — start with R2E-Gym + SWE-bench Verified runner.
3. Source private holdout candidates: 50–100 GitHub issues opened after the candidate base models' training cutoffs, in actively maintained Python/TS/Rust/Go repos with green CI. Manual curation, no shortcuts.
4. Provision GPU access (Lambda / RunPod / Together quotes).
5. Update `OPEN_QUESTIONS.md` Q6–Q10 (eval, collab, budget, licence, done).

After this is done, Phase 1 starts.
