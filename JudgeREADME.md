# Judge + Harness — Owner Guide (Person B)

**Source of truth:** [`SOW.md`](SOW.md) (sections 0, 2, 5, 6, 8, and Runner parts of 4).

This doc tracks what is done on the Judge/harness side, what you still owe before the deadline, and how the flow maps to code in this repo.

---

## Your flow (Judge + Harness)

```
Benchmark Runner: iteration N
        │
        ▼
Pick next bug patch  (benchmark/bugs/)
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
     return verdict JSON  (+ trajectory log — TODO)
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
| `benchmark/bugs/*.patch` | Seeded bugs (one patch + `#` description per file) |
| `benchmark/manifest.json` | Bug registry (id, class, patch filename, description) |
| `benchmark/fixes/syntax-001.patch` | Canned true-positive fix for pipeline smoke test |
| `contracts/` | Frozen mutation + verdict schemas and examples |
| `harness/sandbox.py` | Tempdir clone, `git apply`, build + test gate |
| `harness/judge.py` | Bug patch → mutation diff → verdict JSON |
| `harness/fake_creator.py` | Mock Creator stub (replace with partner's real Creator) |
| `harness/runner.py` | Orchestrates iteration loop, writes metrics |
| `harness/chart.py` | Matplotlib pass-rate chart from `results/metrics.jsonl` |
| `harness/validate_bugs.py` | Confirms every seeded bug breaks build or tests |
| `harness/generate_patches.py` | Regenerates patch files from git diffs (dev helper) |
| `harness/config.py` | Env-var loader; fails loudly on missing vars |
| `results/metrics.jsonl` | Per-iteration metrics (commit as evidence) |
| `results/pass_rate.png` | Chart (commit as evidence) |
| `.env.example` | Required env var names (never commit `.env`) |

---

## Completed (Day 1 — Jul 6)

### 1. Demo app
- [x] Vite + React app at repo root (`src/App.jsx`)
- [x] Small Node util modules (`lib/stats.js`, `lib/format.js`)
- [x] Vitest suite (`lib/*.test.js`) — 9 tests, all green on clean tree
- [x] Verification command matches SOW: `npm run build && npm test`

### 2. Frozen contracts
- [x] `contracts/mutation.schema.json`
- [x] `contracts/verdict.schema.json`
- [x] `contracts/example_mutation.json`
- [x] `contracts/example_verdict.json`
- [x] `.env.example` with SOW §10 vars

### 3. Sandbox + Judge
- [x] Tempdir clone (excludes harness/python artifacts)
- [x] Apply bug patch, then apply mutation fix diff (`git apply`)
- [x] Subprocess build + test with `SANDBOX_TIMEOUT_S` cap
- [x] Verdict JSON matches contract fields exactly
- [x] Windows-safe subprocess encoding

### 4. Bug seeding (partial)
- [x] **10 / 25** bugs seeded in `benchmark/bugs/`:

| Class | Target (SOW §6) | Done |
|---|---|---|
| Syntax | 6 | 4 (`syntax-001` … `syntax-004`) |
| Off-by-one | 5 | 3 (`offbyone-001` … `offbyone-003`) |
| Null/undefined | 5 | 3 (`null-001` … `null-003`) |
| Wrong API usage | 5 | 0 |
| Async mistakes | 4 | 0 |

- [x] `python -m harness.validate_bugs` — all 10 bugs confirmed to break build or tests

### 5. Runner v0 + metrics
- [x] Fake Creator stub (`harness/fake_creator.py`)
  - Sends `example_mutation.json` shape for every bug
  - One true positive: `syntax-001` uses real canned fix in `benchmark/fixes/`
- [x] Runner loop: fake Creator → real Judge → per-bug attempts
- [x] Writes `results/metrics.jsonl` (SOW Runner metrics shape)
- [x] Generates `results/pass_rate.png` via matplotlib
- [x] Mock smoke run: **1 / 10 passed (10%)** with stub Creator (expected)

---

## Still to do (your backlog)

### Tuesday Jul 7 — must ship (SOW §14 kill criteria)

- [ ] **Seed remaining 15 benchmark bugs**
  - 2 more syntax, 2 off-by-one, 2 null, 5 wrong-API, 4 async
  - Keep one-line `#` description on each patch; update `benchmark/manifest.json`
- [ ] **Seed 5 hold-out bugs** (SOW §6) — never shown during iterations; used once at end
  - Suggest `benchmark/holdout/` separate from `benchmark/bugs/` so Runner never picks them in the training loop
- [ ] **Calibrate difficulty with real Creator**
  - Run iteration 0 with partner's Creator (not fake stub)
  - Target pass rate: **20–45%**
  - Too easy (>60%)? Make bugs harder. Too hard (<20%)? Review bug clarity, not test rules.
- [ ] **Trajectory store** (SOW §7 Level 1 step 2)
  - Log every attempt to `trajectories/iterN/` (bug id, mutation JSON, verdict JSON, wall time)
  - Partner's reflection loop reads failures + successes from here
  - *Not built yet — Runner only writes aggregate metrics today*
- [ ] **Swap fake Creator for real Creator**
  - Replace `harness/fake_creator.py` calls with partner's mutation producer
  - Keep contract shape identical; no field renames

### Wednesday–Thursday

- [ ] **Runner: multi-iteration support**
  - Loop iterations 0→3 (or 0→4), append one line per iteration to `metrics.jsonl`
  - Chart should show the rising line judges expect
- [ ] **Performance**
  - Each sandbox run copies `node_modules` (~2 min for 10 bugs at 1 attempt)
  - Consider shared dependency cache or junction/hardlink strategy before 25×8×4 runs
- [ ] **`regression_detected`**
  - Field exists in verdict contract but is always `false` today
  - Optional: run clean-tree tests in parallel and compare if you want real regression signal

### Friday Jul 10 — demo polish

- [ ] **Live heal opener** (SOW §3 Beat 1) — you own the Judge verify + redeploy half of the theater
  - Observer/Creator injects syntax error → your sandbox verifies fix → page back up
- [ ] **Commit evidence artifacts**
  - `results/metrics.jsonl` + `results/pass_rate.png` on main branch
- [ ] **Root README** (shared) — quickstart, architecture diagram, SOW §2 definition up top

### Integration checklist (when partner is ready)

- [ ] Partner's Creator emits mutation JSON validated against `contracts/mutation.schema.json`
- [ ] Your Judge returns verdict JSON validated against `contracts/verdict.schema.json`
- [ ] End-to-end: one bug fixed through real Creator + real Judge (SOW §13 Day-1 deliverable for both sides)
- [ ] Confirm Fireworks judge *commentary* (optional LLM layer) never overrides test gate — commentary is nice-to-have per SOW §12

---

## How to run (local)

```powershell
# 1. Setup
copy .env.example .env
# Required for harness (fail loudly if missing):
#   SANDBOX_TIMEOUT_S=120
#   BENCHMARK_ATTEMPTS_PER_BUG=8

npm install
pip install -r requirements.txt

# 2. Confirm clean app is green
npm run build
npm test

# 3. Confirm seeded bugs break the gate
$env:SANDBOX_TIMEOUT_S="120"
python -m harness.validate_bugs

# 4. Run mock iteration (fake Creator → real Judge)
$env:SANDBOX_TIMEOUT_S="120"
$env:BENCHMARK_ATTEMPTS_PER_BUG="8"   # use 1 for quick stub smoke
python -m harness.runner

# 5. Regenerate chart from existing metrics
python -m harness.chart
```

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

Today `bugs_total` is **10** until remaining bugs are seeded. `gpu_hours_consumed` is `0.0` on your side until partner wires GPU logging.

---

## SOW timeline reminders (your milestones)

| Day | Your goal |
|---|---|
| **Mon Jul 6** | Repo + contracts + sandbox green via canned Creator stub ✅ (partial: 10/25 bugs) |
| **Tue Jul 7** | Full 25-bug benchmark E2E at iteration 0; calibrate 20–45% baseline; trajectory store |
| **Wed Jul 8** | Playbook loop live on partner side; your Runner re-runs same frozen bugs each iteration |
| **Thu Jul 9** | Hold-out eval run once; support Level 2 go/no-go (not your code) |
| **Fri Jul 10** | Freeze code; demo rehearsal; metrics + chart committed |
| **Sat Jul 11** | Submit — nothing new ships |

**Kill criteria (Tue):** if E2E isn't green by end of day, cut to 3 bug classes and 15 bugs (SOW §14).

---

## Open decisions / flags

| Item | Status |
|---|---|
| SOW filename | `SOW.md` and `overall project sow.md` both exist — pick one canonical name for the team |
| JS-only vs JS+Python benchmark | SOW §17 defaults JS-only unless you object by Tuesday — current app is JS-only |
| Fake Creator attempt waste | Stub resends the same bad diff on attempts 2–8; harmless for mock, real Creator fixes this |
| Baseline commit | Clean demo app was committed to generate accurate git diffs for patches — coordinate with partner on branch history |

---

## Definition of done (Judge half)

You are done when:

1. **25 + 5 hold-out** bugs seeded and validated
2. **Real Creator** plugged in; iteration-0 pass rate calibrated to **20–45%**
3. **Runner** runs full iterations unattended; metrics + chart committed
4. **Trajectories** logged per attempt for partner's reflection loop
5. **Verdict gate** stays binary — build + tests only, no LLM override
6. **Live heal** demo path works with partner's Creator for Beat 1

The product is the harness and the improvement curve, not the bug fixer itself (SOW §0).
