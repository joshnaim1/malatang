# Benchmark evidence provenance

This document records what is committed in this repository, what is missing, and known integrity gaps. **No historical evidence was repaired, regenerated, or invented for this audit.**

## Hardware and stack (AMD notebook — authoritative runtime)

| Item | Value |
|------|--------|
| Platform | [AMD AI Notebooks](https://notebooks.amd.com/hackathon) (JupyterLab) |
| GPU | AMD Radeon Pro W7900 class (`gfx1100`, ~48 GB VRAM) |
| Inference | ROCm 7.2 + vLLM 0.16 + `Qwen/Qwen2.5-Coder-7B-Instruct` |
| Creator endpoint | `http://localhost:8090/v1` |
| Reflection | Fireworks API (`accounts/fireworks/models/glm-5p2`) |
| Judge gate | `npm run build && npm test` in tempdir sandbox (no LLM override) |

## Committed metric rows (`results/metrics.jsonl`)

| Iteration | Playbook | bugs_passed | pass_rate | total_llm_calls | Trajectory dir (notebook) |
|-----------|----------|-------------|-----------|-----------------|---------------------------|
| 0 | v0 | 10/25 | 40% | 139 | `trajectories/iter0/` |
| 1 | v1 | 10/25 | 40% | 142 | `trajectories/iter1/` |
| 2 | v2 | 9/25 | 36% | 154 | `trajectories/iter2/` |
| 3 | v3 | 12/25 | 48% | 133 | `trajectories/iter3/` |

Hold-out (not in training curve): `results/holdout.jsonl` — 3/5 (60%) with playbook v3, 28 LLM calls. Trajectories: `trajectories/holdout/` on notebook.

**Campaign summary:** final training pass rate went from **40% → 48%**; hold-out **60%**. Intermediate steps were **not monotonic** (40% → 40% → 36% → 48%).

## Commands per iteration (notebook)

```bash
cd /workspace/malatang
export SANDBOX_TIMEOUT_S=120
export BENCHMARK_ATTEMPTS_PER_BUG=8

# Iteration 0 (calibration)
python -m scripts.check_vllm
python -m harness.runner --creator live --fresh

# Iteration 1
python -m scripts.reflect --iteration 0          # produced v1 (see provenance below)
python -m harness.runner --creator live --start-iteration 1

# Iteration 2
python -m scripts.reflect --iteration 1        # live Fireworks → v2
python -m harness.runner --creator live --start-iteration 2

# Iteration 3
python -m scripts.reflect --iteration 2        # live Fireworks → v3
python -m harness.runner --creator live --start-iteration 3

# Hold-out (once, after training)
python -m scripts.audit_wins
python -m harness.holdout_eval --creator live
python -m harness.chart
```

## Playbook provenance

| File | Reflection mode | Source trajectories | Used for iteration | Integrity notes |
|------|-----------------|---------------------|------------------|-----------------|
| `playbook/v0.md` | Hand-written baseline | — | 0 | Complete |
| `playbook/v1.md` | **`--dry-run` (not Fireworks)** | `iter0` at dry-run time | 1 | Header says **11 wins / 183 failures (194 attempts)** — see mismatch below |
| `playbook/v2.md` | Live Fireworks (`reflect --iteration 1`) | `iter1` | 2 | **Truncated** — ends inside unclosed ` ```diff ` fence (line 74) |
| `playbook/v3.md` | Live Fireworks (`reflect --iteration 2`) | `iter2` | 3 | **Truncated** — ends mid-sentence in `wrong-api` section (line 58) |

### v1 header vs committed iteration-0 metrics

`playbook/v1.md` opens with:

> Dry-run: 11 wins / 183 failures

Committed `results/metrics.jsonl` iteration 0:

> 10 bugs_passed, 139 total_llm_calls

**Explanation (no relabeling):**

1. **Dry-run header** comes from `creator/reflection.py` counting trajectory JSON files where `accepted: true` (wins) and `accepted: false` (failures) at the moment `scripts.reflect --iteration 0 --dry-run` ran.
2. **Metrics row** comes from `harness/runner.py` after the official iteration-0 benchmark finished: `bugs_passed` is unique bugs healed; `total_llm_calls` counts Creator calls (early accept stops attempts per bug).
3. The dry-run was executed against a trajectory tree reporting **194 attempt files** (11+183), while the committed metrics row reports **139** LLM calls and **10** passes. These are **different snapshots** of iteration-0 evidence. The dry-run playbook was still used for iteration 1 (`--start-iteration 1` loads `v1`).

**Do not claim v1 was Fireworks-generated.** The file title and header state dry-run explicitly.

### v2 / v3 truncation

GitHub copies match the notebook export tarball (same byte sizes and line counts at commit time). Truncation is present in the committed artifacts:

- `v2.md` tail: stops after `@@ -26,5 +26,5 @@` context inside a few-shot diff — no closing ` ``` `.
- `v3.md` tail: stops at “Does `formatToParts` return `fraction` or `decimal`?” — no closing section or few-shots.

Live benchmark runs for iterations 2 and 3 used these truncated playbooks as committed. They were **not** manually repaired for this audit.

## SHA-256 hashes (committed tree at audit time)

See `results/evidence/SHA256SUMS.txt` for the full list.

### GitHub (laptop commit at PR #11)

| Artifact | SHA-256 |
|----------|---------|
| `results/metrics.jsonl` | `6b50642e4589df0197b331c58763e180edc5662aa3f16eccce8aa5cda57eaca1` |
| `results/holdout.jsonl` | `1240250e2b474ab38808c99ad8dbc06fe5cdf886792bfc08e90d532e74ab544a` |
| `results/pass_rate.png` | `6449bce7b01da35f2de11e054b5e604325d93197a567ccb49105c4684f6f633b` |
| `playbook/v1.md` | `432efcc32380d024af71c2f053136a72361aa17202fb9c4ef394aba4e6095c0c` |
| `playbook/v2.md` | `f1baece8d072b213bf55247ccf30362af340d9c2d87e1e8d2342ee1bb5d3b79b` |
| `playbook/v3.md` | `5f017bdae18b4f8f669ab3b4663a88f47199ccd9cc013f8d044c36858958d8da` |

### AMD notebook export (2026-07-12 — authoritative)

| Artifact | SHA-256 | Matches GitHub? |
|----------|---------|-----------------|
| `playbook/v1.md` | `432efcc32380d024af71c2f053136a72361aa17202fb9c4ef394aba4e6095c0c` | Yes |
| `playbook/v2.md` | `f1baece8d072b213bf55247ccf30362af340d9c2d87e1e8d2342ee1bb5d3b79b` | Yes |
| `playbook/v3.md` | `5f017bdae18b4f8f669ab3b4663a88f47199ccd9cc013f8d044c36858958d8da` | Yes |
| `results/metrics.jsonl` | `d8616b9ea66f496ad556371390a615974c35e73709cdc4c2b9636603746b12e8` | **No** — sync notebook file |
| `results/holdout.jsonl` | `e2e2bdbf3cfc3f8353450a39e0115d81de7f625f37e93d38912231cda5f86b51` | **No** — sync notebook file |
| `results/pass_rate.png` | `6449bce7b01da35f2de11e054b5e604325d93197a567ccb49105c4684f6f633b` | Yes |
| `results/evidence/trajectories-archive.tar.gz` | `e8a7554546985a958dd0f4947eb6e8a7e771f58f681d1f8b51d258aa77e5c9c8` | Not yet committed |

**Playbook conclusion:** GitHub copies are **byte-identical** to the notebook. v2/v3 truncation existed on the notebook before transfer; live runs used truncated playbooks.

**Metrics/hold-out conclusion:** Notebook `metrics.jsonl` and `holdout.jsonl` differ from GitHub — replace GitHub copies with notebook exports in a follow-up commit (do not hand-edit).

## Trajectories — notebook export complete, not yet in git

Notebook export (2026-07-12) produced `results/evidence/trajectories-archive.tar.gz` (SHA `e8a75545…`). Transfer to laptop and commit in a follow-up PR.

### `audit_wins` — notebook (2026-07-12)

See `results/evidence/audit_wins_notebook.txt`:

| Directory | Accepted wins checked | Contaminated |
|-----------|----------------------|--------------|
| iter0 | 11 | 0 |
| iter1 | 14 | 0 |
| iter2 | 9 | 0 |
| iter3 | 17 | 0 |
| holdout | 3 | 0 |

**PASS:** no protected-file contamination.

**vs metrics.jsonl `bugs_passed`:** iter0 trajectories show **11** accepted files vs metrics row **10**; iter1 **14** vs **10**; iter3 **17** vs **12**. `audit_wins` counts accepted trajectory JSON files on disk; `bugs_passed` counts unique bugs healed in the official runner row. Extra accepted files likely come from **reruns** writing into the same `trajectories/iterN/` tree without clearing prior attempts. iter2 (9) matches metrics (9).

### `audit_wins` on laptop clone (no trajectories)

See `results/evidence/audit_wins_committed_repo.txt`.

## `results/holdout.jsonl` integrity note

The committed hold-out row is an **aggregate summary only** (no `per_bug` array, no `trajectories/holdout/` in repo). Recover notebook `holdout.jsonl` and `trajectories/holdout/` if per-bug hold-out proof is needed. Do not fabricate per-bug rows.

## What is unavailable in this repository

| Artifact | Status |
|----------|--------|
| `trajectories/iter0` … `iter3` | Notebook only — export script provided |
| `trajectories/holdout/` | Notebook only |
| `results/llm_calls.jsonl` | Gitignored, notebook only |
| Full hold-out per-bug breakdown | Not in committed `holdout.jsonl` |
| Complete `v2.md` / `v3.md` | Truncated in committed copies; originals not recovered |

## Verification commands

```bash
pytest
python -m harness.chart
python -m scripts.audit_wins
python -m harness.validate_bugs
```

Contracts and benchmark patches were not modified in this evidence-integrity pass.
