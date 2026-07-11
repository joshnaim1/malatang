# Malatang — Self-Improving Bug-Fix Agent Harness

**AMD Developer Hackathon ACT II · Unicorn track**

An agent that fixes bugs, measures its pass rate on a fixed benchmark, and gets better between runs — first via a self-written playbook, then (stretch) via fine-tuned weights. **The product is the harness and the improvement curve**, not the bug fixer itself.

Full project spec: [`SOW.md`](SOW.md)

---

## Operational definition of "self-improving"

We claim self-improvement **if and only if** all of the following hold:

1. **Same benchmark.** Every iteration runs the identical, frozen set of seeded bugs.
2. **Automatic verification.** A fix counts as a pass only if the build succeeds and the test suite passes in a sandbox. No human judging, no LLM vibes as ground truth.
3. **Rising pass rate.** Iteration N+1 pass rate > iteration N pass rate, measured on the same set.
4. **Self-modification between runs.** The only thing that changes between iterations is something the system changed about itself (playbook at Level 1; model weights at Level 2 stretch).

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

## Quickstart

### Prerequisites

- Node.js 18+
- Python 3.12
- Git

### Setup

```powershell
git clone https://github.com/joshnaim1/malatang.git
cd malatang
git checkout aaron          # Judge/harness branch (or main when merged)

copy .env.example .env      # fill in values; never commit .env
npm install
pip install -r requirements.txt
```

Required env vars (fail loudly if missing):

| Variable | Purpose |
|---|---|
| `SANDBOX_TIMEOUT_S` | Sandbox build+test timeout (default 120) |
| `BENCHMARK_ATTEMPTS_PER_BUG` | Max fix attempts per bug (default 8) |

See [`.env.example`](.env.example) for full list (Fireworks, vLLM, etc.).

### Verify clean demo app

```powershell
npm run build
npm test                    # 23 vitest tests
```

### Run the harness

```powershell
$env:SANDBOX_TIMEOUT_S="120"
$env:BENCHMARK_ATTEMPTS_PER_BUG="8"

python -m harness.validate_bugs                        # 25 training + 5 hold-out bugs must BREAK
python -m harness.live_heal --bug-id syntax-001 --creator mock   # Beat 1 heal demo (no GPU)
python -m scripts.creator_e2e --bug-id syntax-001 --live       # one bug through live Creator (needs vLLM)
python -m harness.runner --creator fake --fresh        # stub Creator → real Judge → metrics + chart
python -m harness.runner --creator mock --fresh        # Creator pipeline (mock fix, no GPU) → real Judge
python -m harness.runner --creator live --fresh        # real Creator on vLLM → calibrate 20-45% (needs GPU box)
python -m harness.holdout_eval                         # one-shot hold-out eval (run once, at the end)
python -m harness.chart                                # regenerate chart from metrics.jsonl
```

Creator backends: `fake` (self-contained stub), `mock` (Creator pipeline + canned fix, no GPU), `live` (Qwen2.5-Coder-7B on vLLM). The Creator normalizes fix diffs with `--- a/` / `+++ b/` headers before they reach the Judge (`creator/diff_utils.py`). The Judge verdict is always the deterministic build+tests gate.

### AMD notebook (hosted JupyterLab)

GPU access for the hackathon is via [AMD AI Notebooks](https://notebooks.amd.com/hackathon) — run vLLM and the harness on the **same box** over `localhost` (no public IP). Inside the notebook terminal:

```bash
git clone https://github.com/joshnaim1/malatang && cd malatang
bash scripts/notebook_setup.sh    # deps + vLLM on :8090 + health check
python -m harness.live_heal --bug-id syntax-001 --creator live
python -m harness.runner --creator live --fresh
```

See `scripts/notebook_setup.sh` and `.env.example` for required env vars (vLLM + Fireworks).

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
| `scripts/` | Notebook bootstrap, vLLM/Fireworks health checks, Creator e2e |
| `results/` | `metrics.jsonl` + `pass_rate.png` (evidence artifacts) |

---

## Benchmark

- **25 training bugs** across 5 learnable classes (syntax, off-by-one, null, Intl.NumberFormat misuse, async)
- **5 hold-out bugs** — never shown during iterations; run once at the end
- **Calibration target:** iteration-0 pass rate **20–45%** with the real Creator (harden bugs, never loosen tests)

---

## AMD stack (submission axis)

| Component | Role |
|---|---|
| AMD GPU + vLLM | Creator fix-generation (Qwen2.5-Coder-7B); hackathon via [AMD AI Notebooks](https://notebooks.amd.com/hackathon) or MI300X droplet |
| Fireworks API | Reflection + playbook rewriting |
| This repo | Deterministic sandbox verification + benchmark Runner |

---

## License

MIT — see [`LICENSE`](LICENSE).
