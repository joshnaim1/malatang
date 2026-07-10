#!/usr/bin/env bash
# In-notebook bootstrap for notebooks.amd.com/hackathon (MI300X JupyterLab).
#
# Access to the AMD Developer Cloud GPU is via a hosted JupyterLab, not an SSH
# droplet with a public IP (SOW section 11 assumed the latter). So we run vLLM
# and the Creator on the SAME box and talk over localhost. Run this from a
# JupyterLab Terminal inside the environment.
#
# Usage:
#   bash scripts/notebook_setup.sh            # deps + launch vLLM in background
#   bash scripts/notebook_setup.sh --no-serve # deps only (don't start vLLM)
set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VLLM_PORT="${VLLM_PORT:-8090}"
VLLM_API_KEY="${VLLM_API_KEY:-malatang-local-key}"
CREATOR_MODEL="${CREATOR_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
SERVE=1
[ "${1:-}" = "--no-serve" ] && SERVE=0

cd "$REPO_DIR"
echo "[setup] repo: $REPO_DIR"

# 1) Python deps for the Creator half (openai SDK, jsonschema, dotenv).
echo "[setup] installing python deps..."
python -m pip install -q -r requirements.txt

# 2) Ensure .env points vLLM at localhost on this box.
if [ ! -f .env ]; then
  cp .env.example .env
fi
python - <<'PY'
import re, pathlib
p = pathlib.Path(".env"); txt = p.read_text() if p.exists() else ""
def setkv(txt, k, v):
    line = f"{k}={v}"
    if re.search(rf"^{k}=.*$", txt, flags=re.M):
        return re.sub(rf"^{k}=.*$", line, txt, flags=re.M)
    return (txt.rstrip() + "\n" + line + "\n") if txt else line + "\n"
import os
port = os.environ.get("VLLM_PORT", "8090")
key  = os.environ.get("VLLM_API_KEY", "malatang-local-key")
model= os.environ.get("CREATOR_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
txt = setkv(txt, "VLLM_BASE_URL", f"http://localhost:{port}/v1")
txt = setkv(txt, "VLLM_API_KEY", key)
txt = setkv(txt, "CREATOR_MODEL", model)
p.write_text(txt)
print("[setup] .env vLLM values set to localhost")
PY

if [ "$SERVE" -eq 0 ]; then
  echo "[setup] --no-serve: skipping vLLM launch. Done."
  exit 0
fi

# 3) Launch vLLM serving the Creator model (SOW section 11.2), in background.
#    First load downloads weights (minutes). Logs -> vllm.log.
echo "[setup] launching vLLM on :$VLLM_PORT (log: vllm.log)..."
nohup vllm serve "$CREATOR_MODEL" \
  --api-key "$VLLM_API_KEY" \
  --port "$VLLM_PORT" \
  --gpu-memory-utilization 0.90 \
  --max-model-len 16384 \
  > vllm.log 2>&1 &
echo "[setup] vLLM pid: $!"

# 4) Wait for the server to answer /v1/models, then run the health check.
echo "[setup] waiting for vLLM to come up (weights may download first)..."
for i in $(seq 1 120); do
  if curl -s "http://localhost:${VLLM_PORT}/v1/models" \
       -H "Authorization: Bearer ${VLLM_API_KEY}" | grep -q '"id"'; then
    echo "[setup] vLLM is up."
    break
  fi
  sleep 10
done

echo "[setup] running health check..."
python -m scripts.check_vllm
echo "[setup] Done. Try: python -m scripts.creator_e2e --bug-id syntax-001 --live"
