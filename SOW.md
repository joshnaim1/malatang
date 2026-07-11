# Self-Improving Bug-Fix Agent - SOW & Build Guide
**Event:** AMD Developer Hackathon: ACT II (lablab.ai × AMD × NativelyAI)
**Track:** Unicorn (open track, judged on creativity, originality, product potential)
**Team:** 2 people (Creator AI owner + Judge/Harness owner)
**Submission deadline:** July 11, 2026, 15:00 UTC (verify live on the event Schedule tab - lablab shows it in local time)
**Event page:** https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii

---

## 0. Context for agents reading this repo

This file is the single source of truth for the project. If you are an AI agent (Claude, Codex, Cursor, etc.) working in this repo:

- The project is a **measured self-improvement harness** for a bug-fixing agent. The product is the harness and the improvement curve, not the bug fixer itself.
- "Self-improving" has a strict operational definition in this project (Section 2). Do not use the phrase loosely anywhere in code, docs, or the submission.
- All model inference routes through **two backends**: a self-hosted open model on an AMD MI300X GPU (via vLLM, OpenAI-compatible endpoint) and the **Fireworks AI API** (also OpenAI-compatible). Backend selection is per-role (Section 4).
- Secrets are never committed. All credentials come from environment variables listed in Section 10. If an env var is missing, fail loudly with the var name.
- GPU time costs real money/credits. Never leave a droplet running or merely powered off after a work session - powered-off droplets still bill. Destroy or snapshot+destroy (Section 11.6).

---

## 1. One-line pitch

An agent that fixes bugs, measures its own pass rate on a fixed benchmark, and provably gets better between runs - first by rewriting its own strategy playbook, then (stretch goal) by fine-tuning its own weights on its verified wins - all running on AMD MI300X.

The demo is a chart: pass rate at iteration 0, 1, 2, 3, going up, with zero human intervention between iterations.

## 2. Operational definition of "self-improving"

We claim self-improvement if and only if all of the following hold:

1. **Same benchmark.** Every iteration runs the identical, frozen set of seeded bugs.
2. **Automatic verification.** A fix counts as a pass only if the build succeeds and the test suite passes in a sandbox. No human judging, no LLM vibes as ground truth.
3. **Rising pass rate.** Iteration N+1 pass rate > iteration N pass rate, measured on the same set.
4. **Self-modification between runs.** The only thing that changes between iterations is something the system changed about itself:
   - **Level 1 (must-ship):** the Creator's strategy playbook - prompts, few-shot examples mined from its own successful trajectories, tool-use heuristics. Context-space improvement.
   - **Level 2 (stretch):** the model weights - LoRA fine-tune on self-generated, test-verified winning trajectories (rejection sampling / STaR-style loop). Weight-space improvement.

Anything that doesn't meet all four is not called self-improvement in this project. This definition goes verbatim in the first 30 seconds of the demo video.

## 3. Demo narrative (what judges see)

| Beat | What happens |
|---|---|
| 1. Live heal (opener, ~45s) | Demo web app is live. A syntax error is injected, page breaks visibly. Observer detects it from build/console output, Creator generates a fix, Judge sandbox-verifies, auto-deploy, page is back. No human touches anything. This is theater; keep it. |
| 2. Define terms (~30s) | State the operational definition from Section 2, on screen. "Everyone says self-improving. Here's what we mean, and here's the proof." |
| 3. The chart (the pitch, ~60s) | Show pass-rate-per-iteration on the 25-bug benchmark. Iteration 0 baseline → iteration 3. Line goes up. |
| 4. Show what it learned (~45s) | Diff of the playbook between iteration 0 and iteration 3. Concrete strategies it wrote for itself. If Level 2 shipped: base checkpoint vs fine-tuned checkpoint on the same held-out bugs. |
| 5. AMD/infra beat (~20s) | One slide: sampling volume (N bugs × K attempts × M iterations) ran on a self-hosted model on MI300X via vLLM; Fireworks handled Judge/reflection calls. Why the compute mattered, in one sentence. |

Cut from the previous SOW draft: the free-text "make this accessible" / dark-mode path. It dilutes the thesis and burns build time. If it survives anywhere, it's a 10-second aside, not a beat.

## 4. Architecture

```
                      ┌─────────────────────────────────────────┐
                      │              Benchmark Runner            │
                      │  (orchestrates iterations, owns metrics) │
                      └───────┬─────────────────────────┬───────┘
                              │ per-bug task            │ per-iteration
                              ▼                         ▼
   ┌──────────────┐   ┌──────────────┐   mutation   ┌──────────────┐
   │   Playbook    │──▶│  Creator AI  │────JSON────▶│   Judge AI    │
   │ (versioned    │   │ Observer→RCA │             │ Sandbox→Test  │
   │  strategy     │   │ →Planner→Fix │◀───reward───│ →Accept/Reject│
   │  memory)      │   └──────┬───────┘    JSON     └──────┬───────┘
   └──────▲───────┘          │                             │
          │                  │ inference                    │ verified wins
          │           ┌──────▼───────┐              ┌──────▼───────┐
          │           │ MI300X vLLM  │              │  Trajectory   │
          │           │ (self-hosted │              │    Store      │
          │           │  open model) │              └──────┬───────┘
          │           └──────────────┘                     │
          │                                                ▼
   ┌──────┴────────────┐                       ┌──────────────────────┐
   │ Reflection step    │◀──── failures ───────│ Level 2 (stretch):    │
   │ (Fireworks API)    │                      │ LoRA fine-tune on     │
   │ rewrites playbook  │                      │ wins → new checkpoint │
   └────────────────────┘                      │ → reload into vLLM    │
                                               └──────────────────────┘
```

**Backend assignment (rationale: this is the honest AMD story):**
- **Creator fix-generation:** self-hosted open model on MI300X via vLLM. This is where the token volume is (25 bugs × 8–16 samples × 4 iterations), and it's the model we fine-tune in Level 2, so it must be one we control.
- **Judge auxiliary calls + Reflection/playbook rewriting:** Fireworks AI API (bigger frontier-class open model, low volume, high reasoning quality). Pass/fail itself is deterministic (build + tests); the LLM judge layer is qualitative commentary only and never overrides the tests.

**Model choice:** Qwen2.5-Coder-7B-Instruct as the Creator base. Reasons: strong coding baseline for its size, small enough that LoRA fine-tuning on 1× MI300X is comfortable (192 GB HBM is far more than needed - LoRA on 7–8B class models is well within a single MI300X, AMD's own tutorials fine-tune 8B-class models on one card), not gated on Hugging Face (no Meta license wall, unlike Llama). Fallback: Qwen2.5-Coder-14B-Instruct if 7B saturates the benchmark too fast.

## 5. Interfaces (freeze these first)

**Creator → Judge (mutation):**
```json
{
  "mutation": {
    "iteration": 2,
    "playbook_version": "v2",
    "bug_id": "syntax-012",
    "attempt": 5,
    "type": "code",
    "trigger": "benchmark | live_error",
    "file": "src/App.jsx",
    "diff": "unified diff",
    "reasoning": "one-line strategy note",
    "model": "qwen2.5-coder-7b | checkpoint-iter2"
  }
}
```

**Judge → Creator (verdict):**
```json
{
  "bug_id": "syntax-012",
  "attempt": 5,
  "accepted": true,
  "build_passed": true,
  "tests_passed": true,
  "regression_detected": false,
  "wall_time_s": 41.2,
  "notes": "restored missing brace, all 6 tests green"
}
```

Changes from the previous draft: added `iteration`, `playbook_version`, `bug_id`, `attempt`, `model`. Removed the free-floating `reward: 0.91` - reward is now a real number computed by the Runner: **pass rate over the benchmark**, not a per-mutation vibe score. Per-mutation acceptance is binary (tests pass), which is defensible under judge questioning.

**Runner → metrics (per iteration):**
```json
{
  "iteration": 2,
  "playbook_version": "v2",
  "model_checkpoint": "base",
  "bugs_total": 25,
  "bugs_passed": 14,
  "pass_rate": 0.56,
  "attempts_per_bug": 8,
  "total_llm_calls": 200,
  "gpu_hours_consumed": 1.8
}
```
Metrics land in `results/metrics.jsonl`. The chart is generated from this file. Commit it - it's evidence.

**Contracts are repo artifacts, not a verbal agreement:**
- Commit them to `contracts/` as `mutation.schema.json` and `verdict.schema.json` (JSON Schema), plus two literal valid examples: `contracts/example_mutation.json` and `contracts/example_verdict.json`.
- The example files double as mock data: Person B's fake Creator sends `example_mutation.json` verbatim, Person A's fake Judge returns `example_verdict.json` with randomized `accepted`.
- After the day-1 freeze, any contract change requires a PR approved by the other teammate. No silent field renames.

## 6. Benchmark design

- **25 seeded bugs** in one small real-ish app (a Vite + React app plus a small Python/Node utility module with an actual test suite). One repo, one branch per bug or a patch file per bug in `benchmark/bugs/`.
- **Bug classes (learnable by design - shared failure patterns so the playbook can generalize):**
  1. Syntax errors (missing brace/paren, bad JSX close) - 6 bugs
  2. Off-by-one / boundary errors in loops and slices - 5 bugs
  3. Null/undefined handling (missing guard, optional chaining) - 5 bugs
  4. Wrong API usage of one specific library (consistent misuse pattern) - 5 bugs
  5. Async mistakes (missing await, unhandled rejection) - 4 bugs
- **Verification:** `npm run build && npm test` (or `pytest`) inside a sandbox (subprocess + timeout + temp dir copy of the repo; no container orchestration, per previous SOW's correct instinct).
- **Hold-out set:** 5 additional bugs never seen during any iteration, used once at the end to show the improvement generalizes. This preempts the "you overfit to your benchmark" judge question.
- Difficulty target: baseline (iteration 0) pass rate should land between 20–45%. If baseline is >60%, the bugs are too easy and the line can't go up; make them harder before starting iterations. Calibrate this on day 1.

## 7. The two improvement loops

**Level 1 - Playbook loop (must ship):**
1. Run full benchmark: for each bug, sample up to K=8 fix attempts at temperature ~0.8, stop early on first accept.
2. Store every trajectory (bug, prompt, diff, verdict) in `trajectories/iterN/`.
3. Reflection step (Fireworks): given all failures + all successes for this iteration, rewrite `playbook/vN+1.md` - strategy notes, per-bug-class tactics, and 2–3 few-shot examples selected from this iteration's verified wins.
4. Increment iteration, re-run. Playbook is injected into the Creator's system prompt.
5. 3–4 iterations total. Chart it.

**Level 2 - Weight loop (stretch, decide go/no-go end of day 3):**
1. Collect all accepted trajectories across iterations → SFT dataset (prompt = bug context, completion = winning diff + reasoning).
2. LoRA fine-tune Qwen2.5-Coder-7B on 1× MI300X. Stack: `transformers` + `peft` + `trl` (SFTTrainer) inside the ROCm PyTorch docker image, following AMD's published LoRA fine-tuning tutorials for MI300X (see References). torchtune on ROCm is the alternative if TRL misbehaves.
3. Serve the merged/adapter checkpoint via vLLM, re-run the same benchmark with the *original iteration-0 playbook* (isolates the weight effect from the playbook effect - this matters for honest attribution).
4. Report both curves: playbook-only vs playbook+weights.
- Minimum data bar: if we have fewer than ~60 verified winning trajectories, skip Level 2 (too little data, regression risk) and ship Level 1 + hold-out generalization instead.

## 8. Tech stack (exact)

| Layer | Choice |
|---|---|
| Demo app / benchmark target | Vite + React (JS) + small Node util module w/ vitest tests |
| Orchestration (Runner, Creator, Judge) | Python 3.12, plain asyncio; no agent framework needed |
| LLM client | `openai` Python SDK, pointed at both backends (they're both OpenAI-compatible) |
| Self-hosted inference | vLLM on MI300X (AMD Developer Cloud "vLLM Quick Start" droplet image) |
| Hosted inference | Fireworks AI serverless (`https://api.fireworks.ai/inference/v1`) |
| Fine-tuning (Level 2) | transformers + peft + trl in ROCm PyTorch container on the same droplet class |
| Sandbox | subprocess + timeout + tempdir clone; nothing fancier |
| Metrics/chart | jsonl + matplotlib; commit the PNG |
| Repo | GitHub, public, MIT license (lablab requires original, MIT-compliant submissions) |

## 9. Accounts, credentials, keys, and access - complete checklist

Do these in order. Items marked **[BOTH]** each teammate does; **[ONE]** one account shared via env vars is enough.

### 9.1 lablab.ai **[BOTH]**
- Create/log in to lablab.ai account, register for the ACT II event page, form/join the team on the event page.
- This is also where the project page + submission gets created. No API key involved.

### 9.2 AMD AI Developer Program (ADP) **[BOTH]**
- Sign up via the event page's "Sign up with AMD" flow (creates/links an AMD account and enrolls you in ADP).
- New-member perks to claim: **$100 AMD Developer Cloud credit**, **$50 Fireworks AI API credit**, 1 month DeepLearning.AI Pro. Hackathon participants were also promised additional compute/API credits at launch - check the event page/Discord for how those are granted.
- **Gotcha:** complimentary cloud credits expire ~30 days from deposit. Claim them now; they comfortably cover the event window.

### 9.3 AMD Developer Cloud **[ONE primary, second account as backup credits]**
- Portal: https://amd.digitalocean.com (the AMD Developer Cloud is DigitalOcean-powered; devcloud.amd.com redirects there). Sign in with the AMD/ADP account. GitHub-based login is also supported.
- **Payment method is required on file even when credits cover everything** - the Create GPU Droplet button stays disabled without a card. Add a card, you won't be charged unless credits run out.
- **SSH key:** generate one per teammate (`ssh-keygen -t ed25519`), upload public keys in the console before creating a droplet. No password login exists.
- No API key needed for our purposes - droplet management is via the web console. (A DigitalOcean-style personal access token exists if we later want CLI/API droplet control; not required for MVP.)

### 9.4 Fireworks AI **[ONE]**
- Create account at fireworks.ai, then dashboard → API Keys → Create API key. Shown once; store immediately.
- Endpoint: `https://api.fireworks.ai/inference/v1`, standard OpenAI SDK with `base_url` override. Model IDs look like `accounts/fireworks/models/<model>`; check the serverless catalog for current IDs (the serverless roster rotates - a 404 on a model usually means it was retired).
- Confirm the $50 ADP credit landed under billing before burning tokens.

### 9.5 Hugging Face **[ONE]**
- Account + read-scoped access token (`hf_...`) for model downloads on the droplet (`huggingface-cli login` or `HF_TOKEN` env).
- Qwen2.5-Coder models are not license-gated, so the token is only strictly needed for throughput/rate limits - but set it up anyway so switching to a gated model later isn't blocked.

### 9.6 GitHub **[BOTH]**
- Public repo (this file at its root), MIT `LICENSE` file from day 1.
- Repo secrets (if we add CI later): `FIREWORKS_API_KEY`, `HF_TOKEN`. GPU endpoint stays out of CI.
- No GitHub tokens needed by the agent code itself - the benchmark repo is local, not fetched via API.

### 9.7 Explicitly NOT needed (so nobody wastes time)
- No OAuth flows anywhere in this project. Everything is bearer-token API keys + SSH.
- No cloud provider SDK credentials (GCP/AWS) - deployment target is the droplet itself.
- No database - filesystem jsonl/md is enough for 5 days.
- No Docker registry account - images are pulled public from Docker Hub / ROCm.

## 10. Environment variables (`.env.example` - commit this file, never `.env`)

```bash
# Fireworks (Judge commentary + Reflection)
FIREWORKS_API_KEY=fw_xxx
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
FIREWORKS_MODEL=accounts/fireworks/models/<pick-from-current-catalog>

# Self-hosted Creator model on MI300X
VLLM_BASE_URL=http://<droplet-ip>:8090/v1
VLLM_API_KEY=<random-string-you-set-when-launching-vllm>   # vLLM --api-key flag
CREATOR_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

# Hugging Face (model downloads on the droplet)
HF_TOKEN=hf_xxx

# Runner config
BENCHMARK_ATTEMPTS_PER_BUG=8
BENCHMARK_TEMPERATURE=0.8
SANDBOX_TIMEOUT_S=120
```

Rule for agents: read config only from env / `.env` via dotenv. Any hardcoded key is a bug.

## 11. Infrastructure runbook (AMD Developer Cloud)

### 11.1 Droplet creation
1. Console → GPU Droplets → Create GPU Droplet.
2. **Region:** ATL1 (Atlanta) has the most consistent MI300X availability; try the other region if capacity errors.
3. **Size: single MI300X** ($1.99/hr, 192 GB HBM3). Do NOT pick 8× MI300X ($15.92/hr) - it burns credits 8× faster and nothing in this project needs it.
4. **Image:** `vLLM Quick Start` for inference sessions (preconfigured ROCm + vLLM container). For fine-tuning sessions, either the same droplet with a ROCm PyTorch container pulled on top, or a `ROCm Software` / PyTorch quick-start image.
5. Attach SSH key(s). Create. Provisioning takes ~2–4 minutes; public IP is on the droplet overview page.

### 11.2 Serving the Creator model
```bash
ssh root@<droplet-ip>
# open the port for the API (droplet firewall)
ufw allow 8090
# inside the vLLM environment/container:
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
  --api-key $VLLM_API_KEY \
  --port 8090 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 16384
```
Endpoint is then OpenAI-compatible at `http://<droplet-ip>:8090/v1`. First model load downloads weights (minutes); subsequent restarts are fast because weights are cached on disk.
Prefer an SSH tunnel over an open port when demoing from a laptop: `ssh -N -L 8090:127.0.0.1:8090 root@<droplet-ip>`.

### 11.3 Fine-tuning session (Level 2)
```bash
docker run -it --device=/dev/kfd --device=/dev/dri --group-add video \
  --ipc=host --shm-size 16G \
  rocm/pytorch:latest
pip install transformers peft trl datasets accelerate
# then run scripts/finetune_lora.py (SFTTrainer, LoRA r=16, alpha=32,
# target q/k/v/o projections, 2-3 epochs over verified-win dataset)
```
AMD's ROCm docs have working LoRA-on-MI300X notebooks using exactly this transformers/peft/trl path (References). **Day-1 smoke test:** run one LoRA training step on 10 dummy samples before anything else in the Level 2 workstream. If that fights us for more than half a day, Level 2 is cut and we don't look back.

### 11.4 Monitoring
- `amd-smi` on the droplet for VRAM/utilization (`rocm-smi` on older ROCm).
- vLLM logs for throughput; the Runner logs tokens per call to `metrics.jsonl` for the budget tracker.

### 11.5 Snapshots
- Before destroying a configured droplet, snapshot it (small storage cost) so the environment restores without redoing setup. This is the main defense against ROCm setup time-loss across sessions.

### 11.6 Cost discipline (this bites people)
- **Powered-off droplets still bill** - disk/CPU/RAM/IP stay reserved. Billing stops only when the droplet is **destroyed**.
- End-of-session ritual: push artifacts to GitHub → snapshot → destroy.
- If complimentary credit fully runs out with no card active, the VM and its data get destroyed - another reason nothing important ever lives only on the droplet.

## 12. Credit budget

Assets (per person who claims ADP): $100 ADC + $50 Fireworks; plus whatever launch credits the event grants. Plan against one person's $100 = ~50 MI300X-hours and keep the second person's credits as reserve.

| Line item | Estimate |
|---|---|
| Day-1 setup, vLLM bring-up, benchmark calibration | 4 GPU-hrs |
| Iteration runs: 25 bugs × ≤8 attempts × 4 iterations, plus reruns | 10–14 GPU-hrs |
| Level 2: 2–3 LoRA runs + eval reruns | 8–10 GPU-hrs |
| Demo rehearsal + recording day | 4 GPU-hrs |
| Buffer / mistakes / re-provisioning | 8 GPU-hrs |
| **Total** | **~34–40 GPU-hrs** - inside one $100 grant with margin |

Fireworks: reflection + judge commentary is low thousands of calls at small token counts; $50 is ample. If burn looks high, drop judge commentary (it's a nice-to-have) before touching reflection.

## 13. Team split

| | Person A - Creator & Training | Person B - Judge, Harness & Runner |
|---|---|---|
| Owns | Observer, RCA, planner, fix generation, playbook format + reflection step, Level 2 fine-tuning pipeline | Sandbox, test gate, verdict logic, Benchmark Runner, metrics/chart, bug seeding + calibration, demo app |
| Day-1 deliverable | vLLM endpoint live, one bug fixed end-to-end via canned Judge stub | 25 seeded bugs + sandbox verify loop green via canned Creator stub |
| Research question | How does an agent mine its own wins into strategy? | How do you make verification fast, deterministic, and cheat-proof? |

Both build against the frozen JSON contracts (Section 5) and mock the other side, same as the original plan. That part of the previous SOW was right; keep it.

## 14. Timeline (today = July 6; deadline July 11, 15:00 UTC)

| Day | Goal | Kill criteria |
|---|---|---|
| **Mon Jul 6** | Accounts + credits claimed, repo up (this file, LICENSE, contracts), droplet live, vLLM serving Qwen, LoRA smoke test attempted, bug seeding started | - |
| **Tue Jul 7** | Full benchmark runs end-to-end at iteration 0. Calibrate difficulty to 20–45% baseline. Trajectory store working. | If E2E isn't green by end of day, cut bug classes to 3 and shrink to 15 bugs |
| **Wed Jul 8** | Playbook loop live. Run iterations 0→2. Line must move. | If pass rate is flat after 2 iterations, debug reflection prompt + few-shot selection; this is the top-priority fire |
| **Thu Jul 9** | Iterations 3–4, hold-out eval. **Level 2 go/no-go call** (needs ≥60 verified wins + the smoke test having passed Monday). If go: fine-tune + eval checkpoint. | No-go → invest the day in a better chart, hold-out story, and live-heal opener polish |
| **Fri Jul 10** | Freeze code. Record demo video (script in Section 3), write project page, README, architecture diagram. Full rehearsal incl. live-heal fallback recording. | - |
| **Sat Jul 11** | Submit by ~12:00 UTC (3-hr buffer before the 15:00 UTC cutoff). Nothing new ships today. | - |

## 15. Submission checklist (verify exact requirements on the event page - lablab format)

- [ ] Public GitHub repo, MIT licensed, original work (lablab rule: submissions must be original and MIT-compliant)
- [ ] Demo video (lablab norm is ~5 min max; confirm on event page) following the Section 3 script
- [ ] Project page on lablab with description, cover image, tech tags (AMD, vLLM, ROCm, Fireworks, Qwen)
- [ ] `results/metrics.jsonl` + the pass-rate chart committed as evidence
- [ ] README: quickstart, architecture diagram, the Section 2 definition up top
- [ ] One paragraph explicitly covering AMD stack usage (MI300X + vLLM + which model, Fireworks roles) - this is a judged axis
- [ ] Team members all added on the lablab team page before the deadline
- [ ] Check event page/Discord for any track-specific submission harness or required format (Track 2 had a Docker I/O harness; Unicorn track requirements may differ - confirm early, not on the 10th)

## 16. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| ROCm/fine-tuning environment fights us | Medium | Day-1 LoRA smoke test; hard go/no-go Thursday; Level 1 alone is a complete submission |
| Flat line (playbook loop doesn't converge) | Medium | Learnable bug classes by design; few-shot from verified wins is the highest-leverage lever; can also raise attempts-per-bug |
| Benchmark too easy (baseline >60%) | Medium | Calibrate Tuesday before any iteration counts; harden bugs, not the harness |
| MI300X capacity unavailable in region | Low | Try alternate region; worst case run Creator on Fireworks temporarily and keep MI300X for fine-tuning only (weaker AMD story, still functional) |
| Credit burn overrun | Low | Budget tracker in metrics; destroy-don't-idle ritual; second teammate's credits in reserve |
| Demo-day live-heal flakes | Medium | Pre-recorded fallback clip, rehearsed Friday (kept from original SOW) |
| Model catalog drift on Fireworks (404 on model ID) | Low | Pin model ID day 1; catalog check is one curl |

## 17. Open questions / decision log

- [ ] Confirm Unicorn track has no mandatory submission harness (unlike Track 2's Docker I/O spec)
- [ ] Confirm launch-bonus credits: how granted, how much, where they land
- [ ] Pick exact Fireworks model ID for reflection from the current serverless catalog
- [ ] Decide JS-only benchmark vs JS+Python split (JS-only simplifies sandbox; Python adds generality story) - default JS-only unless Person B objects by Tuesday
- [x] Dark-mode / free-text feature path: **cut** from MVP (2026-07-06)
- [x] Per-mutation scalar reward: **replaced** with binary accept + iteration-level pass rate (2026-07-06)
- [x] Infrastructure pivot: the live hackathon run used **AMD AI Notebooks on an AMD Radeon Pro W7900 (`gfx1100`, 48 GB) with ROCm + vLLM**, not the originally planned MI300X droplet (2026-07-10). Existing infrastructure sections above remain historical planning context.
- [x] Hold-out evidence is isolated in **`results/holdout.jsonl`** so the one-shot generalization result never pollutes the training curve in `results/metrics.jsonl` (2026-07-10).

## 18. References

- Event page: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii
- AMD Developer Cloud overview + credit terms: https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html
- Getting started on AMD Developer Cloud (droplets, images, SSH): https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html
- lablab tutorial - hosting an LLM with vLLM on MI300X: https://lablab.ai/ai-tutorials/amd-developer-cloud-host-llm-vllm
- lablab article - AMD Developer Program perks, courses, credit flow: https://lablab.ai/ai-articles/from-zero-to-ai-builder-amd-developer-program
- Fireworks quickstart (API key, OpenAI compatibility): https://docs.fireworks.ai/getting-started/quickstart
- Fireworks OpenAI-compatibility details: https://fireworks.ai/docs/tools-sdks/openai-compatibility
- ROCm LoRA fine-tuning notebook (transformers/peft/trl, MI300X-tested): https://rocm.docs.amd.com/projects/ai-developer-hub/en/v1.0/notebooks/fine_tune/LoRA_Llama-3.2.html
- ROCm torchtune fine-tuning tutorial (MI300X-tested): https://rocm.docs.amd.com/projects/ai-developer-hub/en/latest/notebooks/fine_tune/torchtune_llama3.html
- ROCm blog - LoRA on a single MI300X (VRAM requirements): https://rocm.blogs.amd.com/artificial-intelligence/llama-lora/README.html
