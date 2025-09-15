#!/usr/bin/env sh
set -eu
# Best-effort enable pipefail if supported by the shell
set -o pipefail 2>/dev/null || true

# This script downloads a Hugging Face file into /models if not present.
# Env vars expected:
# - HF_REPO_ID (required)
# - HF_FILENAME (optional; if unset, does nothing)
# - HF_REVISION (optional; defaults to main)
# - HF_TOKEN (optional)

echo "[llm_init] starting..."

# Quick no-op if HF_FILENAME is unset
if [ "${HF_FILENAME:-}" = "" ]; then
  echo "[llm_init] HF_FILENAME is not set; nothing to do."
  exit 0
fi

mkdir -p /models

# Cleanup: keep only the target .gguf, remove other .gguf files
echo "[llm_init] Cleaning up stale .gguf models in /models (keeping: ${HF_FILENAME}) ..."
for f in /models/*.gguf; do
  [ -e "$f" ] || break
  bn="$(basename "$f")"
  if [ "$bn" = "$HF_FILENAME" ]; then
    echo "[llm_init] keep: $bn"
  else
    echo "[llm_init] remove: $bn"
    rm -f -- "$f" || true
  fi
done

if [ -f "/models/${HF_FILENAME}" ]; then
  echo "[llm_init] Model already present: /models/${HF_FILENAME}"
  ls -lh /models || true
  exit 0
fi

echo "[llm_init] Installing huggingface_hub (with hf_transfer)..."
python -m pip install -q "huggingface_hub[hf_transfer]"

echo "[llm_init] Downloading ${HF_FILENAME} from repo ${HF_REPO_ID} (rev=${HF_REVISION:-main})..."
python - <<'PY'
from huggingface_hub import hf_hub_download
import os, os.path as p, shutil

repo = os.environ.get("HF_REPO_ID")
fn = os.environ.get("HF_FILENAME")
rev = os.environ.get("HF_REVISION", "main")
token = os.environ.get("HF_TOKEN")

if not fn:
    print("HF_FILENAME is not set; nothing to do.")
    raise SystemExit(0)

if not repo:
    print("HF_REPO_ID is not set; cannot download. Exiting.")
    raise SystemExit(1)

path = hf_hub_download(repo_id=repo, filename=fn, revision=rev, token=token)
os.makedirs("/models", exist_ok=True)
dst = f"/models/{fn}"
if p.abspath(path) != p.abspath(dst):
    shutil.copy2(path, dst)
print("[llm_init] Downloaded:", dst)
PY

ls -lh /models || true
echo "[llm_init] done."
