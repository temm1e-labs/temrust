# AUTOMATION — How Claude Code Drives This Autonomously

The user is hands-off. Claude Code is the executor. This document is the protocol.

---

## What the user provides ONCE (≤ 30 min)

1. **Lambda Labs account + API key**
   - Sign up at lambdalabs.com, fund with $500
   - Create API key in dashboard
   - Save key to `~/.config/temllm/lambda.env` (NOT in repo)
2. **HuggingFace write token**
   - Create at huggingface.co/settings/tokens with `write` scope
   - Save to `~/.config/temllm/hf.env`
3. **GitHub Personal Access Token**
   - Create at github.com/settings/tokens with `repo`, `workflow` scopes
   - Save to `~/.config/temllm/gh.env`
4. **Optional: Weights & Biases API key** (free tier sufficient)
   - Save to `~/.config/temllm/wandb.env`
5. **Budget authorisation** (in-session, written): "I authorise up to $500 total for Tem-Rust v1."

After these are in place, Claude Code can launch GPU instances, train, eval, push checkpoints, publish artifacts — without further per-action permission until the $500 cap.

---

## What the user does PERIODICALLY (≤ 15 min/week)

1. **Open a Claude Code session weekly:** "Continue Tem-Rust." Claude reads `STATUS.md` and resumes.
2. **Approve any single transaction > $50** when prompted. Claude will pause and ask.
3. **Review milestone reports** at end of each phase (Claude posts to STATUS.md and pings).
4. **Approve r/rust launch post + crates.io publish** at Phase 5 (only "public ship" actions need user sign-off).

---

## What Claude Code does AUTONOMOUSLY

Within the $500 envelope, Claude Code:

- Provisions Lambda Labs A100 instances via API
- Launches training/inference jobs with auto-shutdown
- Polls HuggingFace for checkpoint completion
- Crawls GitHub for Rust issues (using user's GH token)
- Runs `cargo test` / `cargo check` / `cargo clippy` for verification
- Runs eval harness, produces results, commits to repo
- Builds the CLI tool in Rust
- Quantizes models on local Mac
- Generates the demo gif (via screen recorder script)
- Drafts the r/rust launch post (user approves before publishing)
- Pushes weights to HuggingFace
- Publishes crate to crates.io
- Updates `STATUS.md` after every milestone
- Logs every spend in `BUDGET_LOG.md`

---

## Session Protocol

### First session (Phase 0 kickoff)
1. User: "Authorise $500 for Tem-Rust. Credentials are in ~/.config/temllm/. Go."
2. Claude:
   - Verifies credentials exist (NOT reads them — user pastes when needed for a specific tool call)
   - Provisions first Lambda instance for Phase 0 baseline runs
   - Updates `STATUS.md` to "Phase 0 — running baselines"
   - Checks back via `ScheduleWakeup` when training jobs complete
3. End of session: Claude commits all work to git, writes summary to `STATUS.md`

### Resumption sessions
1. User: "Continue Tem-Rust."
2. Claude:
   - Reads `STATUS.md` (last state)
   - Reads `BUDGET_LOG.md` (current spend)
   - Reads recent git log (what's already done)
   - Continues from the next pending task
3. If a long-running cloud job is in flight: Claude checks its status, resumes monitoring
4. End of session: commit, update STATUS.md

### Milestone reports
At end of each phase, Claude:
1. Runs full eval, dumps to `eval/results/phase_N_final.json`
2. Updates `STATUS.md` with phase-completion summary
3. Pushes to git
4. Notifies user (commit message + summary text in session)
5. Pauses for user review before starting next phase

---

## Long-Running Job Pattern

Training runs are 3–24 hours. Claude Code sessions are shorter. Solution: **launch on cloud, poll for completion.**

### Launch
```python
# scripts/launch_train.py
import lambdalabs
client = lambdalabs.Client(api_key=os.environ["LAMBDA_API_KEY"])

instance = client.launch(
    instance_type="gpu_1x_a100_sxm4",
    region="us-west-1",
    ssh_keys=["temllm-key"],
    file_system_names=["temllm-data"],
    user_data=open("scripts/cloud_init.sh").read(),  # startup script
)
print(f"Launched {instance.id}")
# startup script does: clone repo, run training, push to HF, shutdown
```

### Poll
Claude uses `ScheduleWakeup` with delaySeconds=1800 (30 min) to check:
1. Has the HF model checkpoint appeared?
2. Is the Lambda instance still running (cost monitor)?
3. Did the training log error out?

If checkpoint appears: trigger Phase N+1.
If instance hangs > 2× expected duration: SSH in (via stored key), grab logs, kill, alert user.

### Cloud-init startup script (template)
```bash
#!/bin/bash
set -e
cd /workspace
git clone --depth 1 https://github.com/tem-llm/tem-llm-build .
pip install -r requirements.txt
huggingface-cli login --token "$HF_TOKEN"
wandb login "$WANDB_KEY"
axolotl train configs/sft_v0.yaml || { echo "TRAIN FAILED"; exit 1; }
axolotl push tem-llm/tem-rust-1.7b-v0
echo "DONE" > /workspace/done.flag
sleep 60  # let any final HF uploads finish
shutdown -h now
```

The `shutdown -h now` is critical: Lambda bills until instance halts. Auto-shutdown = no idle charges.

---

## Failure Modes & Recovery

| Failure | Detection | Recovery |
|---|---|---|
| Lambda spot instance preempted | API status check on poll | Re-launch with checkpoint resume; log $loss to BUDGET_LOG |
| Training NaN / loss explosion | wandb alert + log parse | Kill instance, debug config, re-launch with adjusted LR |
| Cargo verification timeout | timeout=30s per task | Mark example as failed, drop from corpus |
| HF rate limit on push | API error | Exponential backoff retry; max 6 attempts |
| GitHub rate limit on crawl | API error 429 | Sleep until reset; resume crawl |
| Cloud GPU price spike | pre-launch price check | Switch to RunPod or vast.ai if Lambda > $2/hr |
| Out of credentials | API auth error | Pause, ask user to refresh tokens |
| Eval script bug | self-test before run | Run on 1 known-good baseline first; abort if score nonsensical |

---

## Files Claude Code Touches

| File | Purpose | Updated by |
|---|---|---|
| `STATUS.md` | Current phase + progress | Claude (every session) |
| `BUDGET_LOG.md` | Spend ledger | Claude (every transaction) |
| `eval/results/*.json` | Per-run eval results | Claude (per eval run) |
| `BASELINES.md` | Aggregated leaderboard | Claude (per phase) |
| `data/` | Datasets | Claude (Phases 1, 3) |
| `outputs/` | Local model checkpoints (gitignored) | Claude (training) |
| `gguf/` | Quantized exports (gitignored) | Claude (Phase 5) |
| `tem-rust-cli/` | CLI source | Claude (Phase 5) |

Files Claude Code does NOT touch:
- `~/.config/temllm/*.env` — credentials, never read into context
- `OPEN_QUESTIONS.md` (after Phase 0 — user-controlled)
- `PLAN.md` / `PIPELINE.md` / `COSTS.md` — locked, only updated by user instruction

---

## Communication

- **Routine progress** → commits to git with descriptive messages
- **Milestone** → STATUS.md update + summary in session text
- **Question** → ask in session, pause action
- **Error needing human** → STATUS.md "BLOCKED" header, summary in session, do not retry destructively
- **Public publication action (HF push, crates.io publish, r/rust post)** → ALWAYS ask before, regardless of budget

---

## What This Looks Like in Practice

**Day 0 (user, 30 min):**
- Sets up Lambda + HF + GitHub credentials
- Says "Authorise $500. Go."

**Day 1–14 (Claude Code, autonomous):**
- Phase 0 baselines done, $20 spent
- Phase 1 data crawl done, 5K examples ready, $0 spent
- STATUS.md and BUDGET_LOG.md updated daily

**Day 15 (user, 5 min):**
- Opens session, sees Phase 1 done. Says "continue."

**Day 15–35 (Claude Code, autonomous):**
- Phase 2 SFT v0 trained, $30 spent
- Phase 3 synthetic generated + v1 trained, $45 spent
- v1 evaluated; meets §0 bar

**Day 36 (user, 5 min):**
- Reviews milestone. Decides to skip Phase 4 (saves $50) and ship.

**Day 37–50 (Claude Code, autonomous):**
- Phase 5: quantize, build CLI, write blog, draft launch post
- Pauses for user approval on r/rust post + crates.io publish

**Day 51 (user, 10 min):**
- Approves launch.
- Tem-Rust-1.7B is live on HuggingFace + crates.io + r/rust.

**Total user time: ≤ 90 min. Total spend: $105–155 + reserve. Total wall time: ~10 weeks.**
