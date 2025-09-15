#!/usr/bin/env sh
set -eu
# Best-effort enable pipefail if supported by the shell
set -o pipefail 2>/dev/null || true

# This script pre-downloads a Sentence-Transformers model into a shared HF cache.
# Expected env vars:
# - EMBEDDING_MODEL (e.g. sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
# - HF_TOKEN (optional)
# - HF_HOME (not required; this script hardcodes /models/hf)

echo "[embeddings_init] starting..."

EMB_MODEL="${EMBEDDING_MODEL:-}"
if [ -z "$EMB_MODEL" ]; then
  echo "[embeddings_init] EMBEDDING_MODEL is not set; nothing to do."
  exit 0
fi

# Hardcode Hugging Face cache root to reduce env dependency
HF_HOME_DIR="/models/hf"
export HF_HOME="$HF_HOME_DIR"
# Align with runtime default structure: cache goes under "$HF_HOME/hub"
HF_HUB_DIR="$HF_HOME_DIR/hub"
mkdir -p "$HF_HUB_DIR"

echo "[embeddings_init] Using HF_HOME=${HF_HOME} (hub=$HF_HUB_DIR)" 

echo "[embeddings_init] Installing huggingface_hub (with hf_transfer support)..."
python -m pip install -q "huggingface_hub[hf_transfer]"

echo "[embeddings_init] Checking local cache first ..."
python - <<'PY'
import os
from huggingface_hub import snapshot_download

model_id = os.environ.get("EMBEDDING_MODEL")
token = os.environ.get("HF_TOKEN")
cache_root = os.path.join(os.environ.get("HF_HOME", "/models/hf"), "hub")

if not model_id:
    print("[embeddings_init] EMBEDDING_MODEL not set; exiting.")
    raise SystemExit(0)

try:
    local_path = snapshot_download(repo_id=model_id, token=token, cache_dir=cache_root, local_files_only=True)
    print(f"[embeddings_init] Cache already present at: {local_path}. Skipping download.")
    raise SystemExit(0)
except Exception:
    print("[embeddings_init] Local cache not found/complete. Will fetch online ...")
PY

echo "[embeddings_init] Snapshot download: ${EMB_MODEL} ..."
python - <<'PY'
import os
from huggingface_hub import snapshot_download

model_id = os.environ.get("EMBEDDING_MODEL")
token = os.environ.get("HF_TOKEN")
cache_root = os.path.join(os.environ.get("HF_HOME", "/models/hf"), "hub")

if not model_id:
    print("[embeddings_init] EMBEDDING_MODEL not set; exiting.")
    raise SystemExit(0)

local_path = snapshot_download(repo_id=model_id, token=token, cache_dir=cache_root)
print(f"[embeddings_init] Model cached at: {local_path}")
PY

echo "[embeddings_init] Done. Current cache tree:"
ls -lR "$HF_HUB_DIR" | awk 'NR<300' || true
echo "[embeddings_init] completed."
