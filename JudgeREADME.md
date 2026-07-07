# Judge + Harness — Owner Guide (Person B)

**Source of truth:** [`SOW.md`](SOW.md) (sections 0, 2, 5, 6, 8, and Runner parts of 4).

This doc tracks what is done on the Judge/harness side, what you still owe before the deadline, and how the flow maps to code in this repo.

---

## Your flow (Judge + Harness)

```
Benchmark Runner: iteration N
        │
        ▼
Pick next bug patch  (benchmark/bugs/ — 25 training bugs)
        │
        ▼
┌───────────────────────────────┐
│  CREATOR SIDE (mocked today)  │  ← partner owns real Creator later
│  Fake Creator → mutation JSON │
└───────────────┬───────────────┘
                │  contracts/example_mutation.json shape
                ▼
┌───────────────────────────────────────────────┐
│  SANDBOX: subprocess + tempdir                │
│  1. Clone demo app                            │
│  2. Apply seeded bug patch + fix diff         │
│  3. npm run build && npm test  (120s cap)     │
└───────────────┬───────────────────────────────┘
                │
                ▼
        Build + tests pass?
           /            \
         yes             no
          │               │
   accepted: true   accepted: false
          │               │
          └───────┬───────┘
                  ▼
     return verdict JSON  (+ trajectory log → trajectories/iterN/)
                  │
                  ▼
     more attempts (<8) or more bugs?
           /              \
         yes               no
          │                 │
     (loop back)     pass rate → metrics.jsonl + chart
                              │
                              ▼
              trajectories → partner's reflection loop

Hold-out bugs (benchmark/holdout/ — 5 bugs) are NEVER run in the training loop.
Use them once at the end for generalization eval (SOW §6).
```

**Calibration rule (SOW §6):** iteration-0 pass rate with the **real** Creator must land at **20–45%**. If baseline is >60%, **harden bugs** — never loosen the test gate.

**Verdict rule (SOW §2):** binary and deterministic. `accepted = build_passed AND tests_passed`. No LLM opinion overrides tests.

---

## What you own vs what you do not touch

| You own | Do not touch |
|---|---|
| Demo web app | Creator AI (Observer, RCA, planner, fix gen) |
| Bug seeding + calibration | Playbook format + reflection step |
| Sandbox (subprocess + timeout + tempdir) | GPU / vLLM / fine-tuning (Level 2) |
| Pass/fail test gate + verdict logic | Anything that changes frozen contract fields |
| Benchmark Runner + metrics/chart | |

All cross-team I/O goes through frozen JSON in [`contracts/`](contracts/). Contract changes require a PR approved by your partner.

---

## Repo map (Judge side)

| Path | Purpose |
|---|---|
| `src/`, `lib/`, `index.html`, `vite.config.js` | Demo app (Vite + React + vitest) |
| `lib/currency.js` | Intl.NumberFormat helpers (wrong-API bug class) |
| `lib/asyncCart.js` | Async cart helpers (async bug class) |
| `benchmark/bugs/*.patch` | **25 training bugs** (one patch + `#` description each) |
| `benchmark/holdout/*.patch` | **5 hold-out bugs** (never in training loop) |
| `benchmark/manifest.json` | Training bug registry |
| `benchmark/holdout/manifest.json` | Hold-out bug registry |
| `benchmark/fixes/syntax-001.patch` | Canned true-positive fix for pipeline smoke test |
| `contracts/` | Frozen mutation + verdict schemas and examples |
| `harness/sandbox.py` | Tempdir clone, node_modules junction, `git apply`, build + test gate |
| `harness/judge.py` | Bug patch → mutation diff → verdict JSON (+ regression signal) |
| `harness/fake_creator.py` | Mock Creator stub (replace with partner's real Creator) |
| `harness/runner.py` | Multi-iteration loop over **training** bugs; logs trajectories + metrics |
| `harness/holdout_eval.py` | One-shot eval over the **hold-out** set (separate from training) |
| `harness/trajectory.py` | Trajectory store — writes every attempt to `trajectories/` |
| `harness/benchmark_io.py` | Shared manifest/patch loaders (training + hold-out) |
| `harness/chart.py` | Matplotlib pass-rate chart from `results/metrics.jsonl` |
| `harness/validate_bugs.py` | Confirms all 25 + 5 bugs break build or tests |
| `harness/generate_patches.py` | Regenerates patches from git diffs (dev helper) |
| `harness/config.py` | Env-var loader; fails loudly on missing vars |
| `trajectories/iterN/` | Per-attempt JSON records for the reflection loop (gitignored) |
| `trajectories/holdout/` | Hold-out attempt records |
| `results/metrics.jsonl` | Per-iteration metrics (commit as evidence) |
| `results/holdout_metrics.jsonl` | Hold-out eval results |
| `results/pass_rate.png` | Chart (commit as evidence) |
| `.env.example` | Required env var names (never commit `.env`) |

---

## Completed

### 1. Demo app
- [x] Vite + React app at repo root (`src/App.jsx`)
- [x] Node util modules: `lib/stats.js`, `lib/format.js`, `lib/currency.js`, `lib/asyncCart.js`
- [x] Vitest suite — **23 tests**, all green on clean tree
- [x] Verification command matches SOW: `npm run build && npm test`

### 2. Frozen contracts
- [x] `contracts/mutation.schema.json` + `contracts/verdict.schema.json`
- [x] `contracts/example_mutation.json` + `contracts/example_verdict.json`
- [x] `.env.example` with SOW §10 vars

### 3. Sandbox + Judge
- [x] Tempdir clone (excludes harness/python artifacts)
- [x] Apply bug patch, then apply mutation fix diff (`git apply`)
- [x] Subprocess build + test with `SANDBOX_TIMEOUT_S` cap
- [x] Verdict JSON matches contract fields exactly
- [x] Windows-safe subprocess encoding

### 4. Bug seeding — training set (25/25)
- [x] All SOW §6 classes covered:

| Class | Target | Seeded |
|---|---|---|
| Syntax | 6 | 6 (`syntax-001` … `syntax-006`) |
| Off-by-one | 5 | 5 (`offbyone-001` … `offbyone-005`) |
| Null/undefined | 5 | 5 (`null-001` … `null-005`) |
| Wrong API (Intl.NumberFormat) | 5 | 5 (`api-001` … `api-005`) |
| Async mistakes | 4 | 4 (`async-001` … `async-004`) |

### 5. Hold-out set (5/5)
- [x] `benchmark/holdout/` — 5 bugs, excluded from `harness/runner.py`
- [x] Validated via `python -m harness.validate_bugs` (training + hold-out)

| ID | Class |
|---|---|
| `holdout-001` | syntax |
| `holdout-002` | off-by-one |
| `holdout-003` | null-handling |
| `holdout-004` | wrong-api |
| `holdout-005` | async |

### 6. Runner + metrics
- [x] Fake Creator stub (`harness/fake_creator.py`) — one true positive on `syntax-001`
- [x] Runner loop: fake Creator → real Judge → per-bug attempts (early accept)
- [x] **Multi-iteration support** — `--iterations N`, `--fresh`, `--start-iteration`
- [x] Writes `results/metrics.jsonl` + `results/pass_rate.png`
- [x] Re-run at 25 bugs — baseline metrics + chart regenerated (stub: 1/25)

### 7. Trajectory store
- [x] `harness/trajectory.py` — every attempt written to `trajectories/iterN/{bug}_attempt{n}.json`
- [x] Records full mutation payload, verdict, bug class, timestamp
- [x] Per-iteration `summary.json`; hold-out records under `trajectories/holdout/`
- [x] Feeds partner's reflection loop (read-only from their side)

### 8. Hold-out eval
- [x] `harness/holdout_eval.py` — one-shot over `benchmark/holdout/`, **never** in training loop
- [x] Writes `results/holdout_metrics.jsonl` + `trajectories/holdout/`

### 9. Sandbox performance
- [x] `node_modules` **junctioned** (Windows) / symlinked (POSIX) instead of copied — no per-attempt copy
- [x] build/test invoked via direct `node` binaries, skipping the `npm` wrapper startup
- [x] ~10s/bug locally (down from ~12s, and no disk churn from 800 node_modules copies at full scale)

### 10. Regression signal
- [x] `regression_detected` is now real: `build_passed AND NOT tests_passed` (compiles but behaviour wrong)
- [x] Never overrides the binary gate — diagnostic flag only (verified: `null-002` → `true`, accepted fixes → `false`)

---

## Still to do (your backlog)

### Blocked on real Creator (integration)

- [ ] **Calibrate difficulty with real Creator** — iteration-0 pass rate **20–45%**
- [ ] **Swap fake Creator for real Creator** — same contract shape, no field renames
- [ ] **Real multi-iteration run** — line only rises with a self-improving Creator (harness never fakes it)

### Friday Jul 10 — demo polish

- [ ] **Live heal opener** (SOW §3 Beat 1) — Judge verify + redeploy half
- [ ] **Commit latest evidence artifacts** (`metrics.jsonl` + `pass_rate.png`) after calibration
- [x] **Root README** — [`README.md`](README.md) at repo root

### Integration checklist (when partner is ready)

- [ ] Partner's Creator validates against `contracts/mutation.schema.json`
- [ ] Judge verdict validates against `contracts/verdict.schema.json`
- [ ] End-to-end: real Creator + real Judge on one bug
- [ ] Fireworks commentary never overrides test gate

---

## How to run (local)

```powershell
copy .env.example .env
npm install
pip install -r requirements.txt

npm run build && npm test

$env:SANDBOX_TIMEOUT_S="120"
$env:BENCHMARK_ATTEMPTS_PER_BUG="8"

python -m harness.validate_bugs                    # ~6 min — all 30 bugs must BREAK
python -m harness.runner --fresh --iterations 1    # fake Creator → real Judge → metrics + chart
python -m harness.runner --iterations 3            # multi-iteration (plumbing; line rises only with real Creator)
python -m harness.holdout_eval                     # one-shot hold-out eval (run once, at the end)
python -m harness.chart                            # regenerate chart from metrics.jsonl

python harness/generate_patches.py   # dev: regenerate patches after clean-source edits
```

Runner flags: `--iterations N`, `--start-iteration K`, `--model-checkpoint LABEL`, `--fresh` (truncate metrics), `--no-chart`.

---

## Metrics contract (what Runner writes)

Each iteration appends one JSON line to `results/metrics.jsonl`:

```json
{
  "iteration": 0,
  "playbook_version": "v0",
  "model_checkpoint": "base",
  "bugs_total": 25,
  "bugs_passed": 14,
  "pass_rate": 0.56,
  "attempts_per_bug": 8,
  "total_llm_calls": 200,
  "gpu_hours_consumed": 1.8
}
```

`bugs_total` is **25** (training set only). Hold-out bugs are evaluated separately.

---

## SOW timeline reminders

| Day | Your goal |
|---|---|
| **Mon Jul 6** | Repo + contracts + sandbox + **25 + 5 bugs seeded** ✅ |
| **Tue Jul 7** | Harness ready ✅ (trajectory store, multi-iteration runner, hold-out eval, perf, regression) — E2E + calibrate 20–45% once real Creator lands |
| **Wed Jul 8** | Partner playbook loop; Runner re-runs same frozen bugs |
| **Thu Jul 9** | Hold-out eval once |
| **Fri Jul 10** | Freeze code; demo rehearsal; evidence committed |
| **Sat Jul 11** | Submit |

---

## Definition of done (Judge half)

1. **25 + 5 hold-out** bugs seeded and validated ✅
2. **Real Creator** plugged in; iteration-0 pass rate **20–45%**
3. **Runner** runs full iterations unattended; metrics + chart committed — plumbing ✅ (needs real Creator for the curve)
4. **Trajectories** logged per attempt for partner's reflection loop ✅
5. **Verdict gate** stays binary — build + tests only ✅
6. **Live heal** demo path works for Beat 1
7. **Hold-out eval** run once to show generalization

The product is the harness and the improvement curve, not the bug fixer itself (SOW §0).
