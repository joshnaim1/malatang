#!/usr/bin/env bash
# Export benchmark evidence from the AMD notebook without modifying originals.
# Run from repo root on the notebook after iterations 0-3 and hold-out complete.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/results/evidence"
mkdir -p "$OUT"

echo "== Playbook fingerprints =="
sha256sum playbook/v1.md playbook/v2.md playbook/v3.md
wc -l playbook/v1.md playbook/v2.md playbook/v3.md
echo "--- v2 tail ---"
tail -n 5 playbook/v2.md
echo "--- v3 tail ---"
tail -n 5 playbook/v3.md

echo "== Metrics / hold-out =="
sha256sum results/metrics.jsonl results/holdout.jsonl results/pass_rate.png

ARCHIVE="$OUT/trajectories-archive.tar.gz"
echo "== Archiving trajectories (read-only copy into tarball) =="
tar czf "$ARCHIVE" \
  trajectories/iter0 \
  trajectories/iter1 \
  trajectories/iter2 \
  trajectories/iter3 \
  trajectories/holdout \
  2>/dev/null || {
    echo "WARN: some trajectory directories missing; archive contains what exists"
    tar czf "$ARCHIVE" trajectories/ 2>/dev/null || true
  }

if [[ -f "$ARCHIVE" ]]; then
  sha256sum "$ARCHIVE" | tee -a "$OUT/SHA256SUMS.txt"
  echo "Wrote $ARCHIVE"
fi

echo "== audit_wins =="
python -m scripts.audit_wins | tee "$OUT/audit_wins_notebook.txt"

echo "Done. Transfer results/evidence/ to laptop and commit trajectories-archive.tar.gz + audit output."
