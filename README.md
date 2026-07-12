# Malatang — Self-Improving Bug-Fix Agent Harness

**AMD Developer Hackathon ACT II · Unicorn track**

An agent that fixes bugs, measures its pass rate on a frozen benchmark, and gets better between runs by rewriting its own strategy playbook from sandbox-verified wins and failures. **The product is the harness and the measured improvement curve, not the bug fixer itself.**

## What we built

Malatang is a **self-improving bug-fix harness** — not a one-off demo app:

| Piece | What it does |
|-------|----------------|
| **Frozen benchmark** | 25 training + 5 hold-out bugs as unified diffs against a small Next.js app (`benchmark/`) |
| **Deterministic Judge** | Temp sandbox → apply bug + fix → `npm run build && npm test`; binary pass/fail (`harness/judge.py`, `harness/sandbox.py`) |
| **Creator pipeline** | Observer → RCA → Planner → Fix, guided by a versioned playbook (`creator/`, `playbook/`) |
| **Reflection loop** | Mine verified trajectories into the next playbook (`scripts/reflect.py`, `creator/reflection.py`) |
| **Metrics & evidence** | Per-iteration pass rate → `results/metrics.jsonl` + chart; trajectories → `trajectories/iterN/` |

All benchmark inference runs on **approved hackathon compute** (AMD AI Notebooks + Fireworks). Development of the harness used **Cursor, Claude, and Codex** as pair-programming assistants (see [External services](#external-services--tools)).

## Operational definition of "self-improving"

Malatang claims self-improvement **if and only if** all four conditions hold:

1. **Same benchmark.** Every iteration runs the identical, frozen set of seeded bugs.
2. **Automatic verification.** A fix counts as a pass only if the build succeeds and the test suite passes in a sandbox. No human judging, no LLM vibes as ground truth.
3. **Rising pass rate.** Iteration N+1 pass rate > iteration N pass rate, measured on the same set (the SOW target; see submitted results below for what we actually measured).
4. **Self-modification between runs.** The only thing that changes between iterations is something the system changed about itself (playbook at Level 1; model weights at Level 2 stretch).

![Benchmark pass rate by iteration](results/pass_rate.png)

The chart is generated only from `results/metrics.jsonl`. Full project spec: [`SOW.md`](SOW.md). Evidence audit: [`docs/BENCHMARK_EVIDENCE_PROVENANCE.md`](docs/BENCHMARK_EVIDENCE_PROVENANCE.md).

### Submitted benchmark results (AMD notebook, honest)

On the frozen 25-bug training set, pass rate went **40% → 40% → 36% → 48%** — intermediate iterations were noisy and **not** monotonically improving. Final training pass rate improved from **40% to 48%**. On the five-bug hold-out (run once with playbook v3), pass rate was **60%** (3/5).

- **`playbook/v1.md` is a dry-run** (`scripts.reflect --iteration 0 --dry-run`), not a live Fireworks rewrite. Do not claim otherwise.
- Committed `playbook/v2.md` and `playbook/v3.md` are **truncated** in the repository; live runs used them as-is. See the provenance doc for SHA-256 hashes and notebook export steps.
- Production trajectories are **not** in git; use `scripts/notebook_export_evidence.sh` on the notebook to archive them.

---

## Architecture

```
                 Benchmark Runner  (metrics, iterations)
                        │
         mutation JSON   │   verdict JSON
    Creator AI ◀───────┼───────▶ Judge AI
    (playbook + vLLM)  │        (sandbox + tests)
                        │
                 trajectories → reflection → new playbook
```

- **Creator → Judge:** `contracts/mutation.schema.json`
- **Judge → Creator:** `contracts/verdict.schema.json`
- **Runner metrics:** `results/metrics.jsonl` → `results/pass_rate.png`

Team split and runbooks: [`SOW.md`](SOW.md) · Judge/harness guide: [`JudgeREADME.md`](JudgeREADME.md)

---

## Main code path

| Step | What happens | Code |
|------|----------------|------|
| 1 | Load frozen bugs, orchestrate iterations | `harness/runner.py` |
| 2 | Creator reads playbook, calls vLLM, emits fix JSON | `creator/pipeline.py` → `harness/creator_backend.py` |
| 3 | Judge clones app, applies patches, runs build + tests | `harness/judge.py` → `harness/sandbox.py` |
| 4 | Record trajectory + verdict | `harness/trajectory.py` → `trajectories/iterN/` |
| 5 | Reflect on wins/failures, write next playbook | `scripts/reflect.py` → `playbook/vN.md` |
| 6 | Append metrics, regenerate chart | `results/metrics.jsonl` → `harness/chart.py` |

**Primary entry points:**

```bash
python -m harness.runner --creator live --fresh    # full benchmark loop (notebook)
python -m harness.validate_bugs                      # confirm all 30 bugs break (~6 min)
python -m harness.holdout_eval --creator live        # one-shot hold-out (run once at end)
```

---

## Quickstart

### Prerequisites

- Node.js 18+
- Python 3.12
- Git

### Setup

```bash
git clone https://github.com/joshnaim1/malatang.git
cd malatang
cp .env.example .env        # fill in values; never commit .env
npm install
python -m pip install -r requirements.txt
```

Required env vars (fail loudly if missing):

| Variable | Purpose |
|---|---|
| `SANDBOX_TIMEOUT_S` | Sandbox build+test timeout (default 120) |
| `BENCHMARK_ATTEMPTS_PER_BUG` | Max fix attempts per bug (default 8) |

See [`.env.example`](.env.example) for full list (Fireworks, vLLM, etc.).

### Verify locally without GPU or API calls

```bash
npm run build
npm test                    # 23 vitest tests
pytest
python -m harness.validate_bugs
python -m harness.live_heal --bug-id syntax-001 --creator mock
python -m harness.runner --creator fake --fresh
```

Creator backends: `fake` (self-contained stub), `mock` (Creator pipeline + canned fix, no GPU), `live` (Qwen2.5-Coder-7B on vLLM). The Creator normalizes fix diffs with `--- a/` / `+++ b/` headers before they reach the Judge (`creator/diff_utils.py`). The Judge verdict is always the deterministic build+tests gate.

### Live run on AMD AI Notebooks

The run used an **AMD Radeon Pro W7900 (`gfx1100`, 48 GB)** through [AMD AI Notebooks](https://notebooks.amd.com/hackathon), with ROCm and vLLM serving `Qwen/Qwen2.5-Coder-7B-Instruct`. vLLM and the harness run on the same JupyterLab machine over `localhost:8090`; Fireworks handles the lower-volume reflection call.

```bash
git clone https://github.com/joshnaim1/malatang && cd malatang
cp .env.example .env              # fill Fireworks values; never commit
npm install
bash scripts/notebook_setup.sh
python -m scripts.check_vllm
python -m harness.live_heal --bug-id syntax-001 --creator live
python -m harness.runner --creator live --fresh
python -m scripts.audit_wins
python -m scripts.reflect --iteration 0
python -m harness.runner --creator live --start-iteration 1

# Repeat reflect + runner for subsequent iterations, then evaluate hold-out once:
python -m scripts.audit_wins
python -m harness.holdout_eval --creator live
python -m harness.chart
```

`scripts.reflect --dry-run` validates plumbing but is explicitly not evidence of self-improvement. Hold-out results are isolated in `results/holdout.jsonl`; they never enter the training curve.

### Live pipeline dashboard (demo GUI)

A lightweight web UI polls `results/metrics.jsonl` and `trajectories/iterN/` every 2 seconds so judges can watch iteration progress during a live run.

```bash
python -m scripts.dashboard_server
# or: bash scripts/demo_dashboard.sh

# On the notebook, bind publicly if needed:
python -m scripts.dashboard_server --host 0.0.0.0 --port 8765
```

Open `http://127.0.0.1:8765/` while the runner is active. The dashboard shows pass-rate curve, pipeline step status, active-iteration progress, recent attempt verdicts, hold-out results, and a **Run iteration** button that launches `python -m harness.runner` in the background (`POST /api/run`).

---

## Repo layout

| Path | What |
|---|---|
| `src/`, `lib/` | Vite + React demo app + vitest suite |
| `benchmark/bugs/` | 25 training bugs (patch files) |
| `benchmark/holdout/` | 5 hold-out bugs (eval only, not in training loop) |
| `contracts/` | Frozen JSON schemas + examples |
| `creator/` | Creator pipeline (Observer → Fix → mutation); diff normalization |
| `harness/` | Sandbox, Judge, Runner, chart (Python) |
| `scripts/` | Notebook bootstrap, vLLM/Fireworks health checks, Creator e2e, pipeline dashboard |
| `dashboard/` | Live iteration progress GUI (served by `scripts/dashboard_server.py`) |
| `results/` | Training `metrics.jsonl`, isolated `holdout.jsonl`, and `pass_rate.png` |

---

## Benchmark

- **25 training bugs** across 5 learnable classes (syntax, off-by-one, null, Intl.NumberFormat misuse, async)
- **5 hold-out bugs** — never shown during iterations; run once at the end
- **Calibration target:** iteration-0 pass rate **20–45%** with the real Creator (harden bugs, never loosen tests)

---

## AMD & approved compute usage

All production benchmark runs used **AMD-provided hackathon infrastructure** and **Fireworks** (approved API partner). No other paid inference APIs were used in the benchmark loop.

| Component | Role |
|---|---|
| [AMD AI Notebooks](https://notebooks.amd.com/hackathon) | Hackathon JupyterLab environment |
| AMD Radeon Pro W7900 (`gfx1100`, 48 GB) | GPU for self-hosted Creator inference |
| ROCm + vLLM | OpenAI-compatible local server on `localhost:8090` |
| `Qwen/Qwen2.5-Coder-7B-Instruct` | Creator model (downloaded via Hugging Face token) |
| Fireworks API | Reflection + playbook rewriting (lower volume than Creator sampling) |
| This repo | Deterministic sandbox verification, benchmark Runner, metrics |

**Sampling volume:** 25 bugs × up to 8 attempts × 4 training iterations, plus hold-out eval — Creator calls hit vLLM on the W7900; reflection calls hit Fireworks. See [`scripts/notebook_setup.sh`](scripts/notebook_setup.sh) for notebook bootstrap and [`scripts/check_vllm`](scripts/check_vllm.py) for health checks.

---

## External services & tools

### Runtime (benchmark & inference)

| Service | Used for | Config |
|---------|----------|--------|
| AMD AI Notebooks | GPU notebook environment | Event-provided access |
| vLLM (self-hosted) | Creator fix generation | `VLLM_BASE_URL`, `VLLM_API_KEY`, `CREATOR_MODEL` in [`.env.example`](.env.example) |
| Fireworks | Playbook reflection / rewriting | `FIREWORKS_API_KEY`, `FIREWORKS_MODEL` |
| Hugging Face | Model weight download on notebook | `HF_TOKEN` |

### Development (building this repo)

| Tool | Used for |
|------|----------|
| [Cursor](https://cursor.com) | IDE + agent-assisted editing during the hackathon |
| [Claude](https://anthropic.com) (Anthropic) | Architecture, docs, and harness implementation via Cursor agents |
| [Codex](https://openai.com) (OpenAI) | Code generation and debugging via Cursor agents |

These development assistants helped author the harness, schemas, and documentation. **They are not part of the benchmark inference path** — measured pass rates come only from vLLM (Creator) and Fireworks (reflection), with verification entirely in the local sandbox.

---

## Original work

- **Harness, schemas, and benchmark** — designed and implemented by Team Malatang; not a fork of an existing self-improvement framework.
- **Bug corpus** — 30 seeded defects across learnable classes, each validated to break build/tests before any fix is applied.
- **Playbooks** — written by the reflection loop from the system's own verified trajectories, not hand-curated cheat sheets.
- **Evidence** — metrics, trajectories, and provenance documented in [`docs/BENCHMARK_EVIDENCE_PROVENANCE.md`](docs/BENCHMARK_EVIDENCE_PROVENANCE.md); we report non-monotonic intermediate iterations honestly.

Demo app under `src/` is a minimal Vite + React target for patches; the submission artifact is the **measurement harness and improvement curve**.

---

## License

MIT — see [`LICENSE`](LICENSE).
