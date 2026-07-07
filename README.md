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

python -m harness.validate_bugs   # 25 training + 5 hold-out bugs must BREAK
python -m harness.runner          # fake Creator → real Judge → metrics + chart
python -m harness.chart           # regenerate chart from metrics.jsonl
```

---

## Repo layout

| Path | What |
|---|---|
| `src/`, `lib/` | Vite + React demo app + vitest suite |
| `benchmark/bugs/` | 25 training bugs (patch files) |
| `benchmark/holdout/` | 5 hold-out bugs (eval only, not in training loop) |
| `contracts/` | Frozen JSON schemas + examples |
| `harness/` | Sandbox, Judge, Runner, chart (Python) |
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
| MI300X + vLLM | Creator fix-generation (Qwen2.5-Coder-7B) |
| Fireworks API | Reflection + optional Judge commentary |
| This repo | Deterministic sandbox verification + benchmark Runner |

---

## License

MIT — see [`LICENSE`](LICENSE).
