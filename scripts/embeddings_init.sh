#!/usr/bin/env sh
set -eu
# Best-effort enable pipefail if supported by the shell
set -o pipefail 2>/dev/null || true

# This script pre-downloads embedding and reranker models into a shared HF cache.
# Expected env vars:
# - EMBEDDING_MODEL (e.g. intfloat/multilingual-e5-base)
# - RERANKER_MODEL (e.g. BAAI/bge-reranker-base)
# - HF_TOKEN (optional)
# - HF_HOME (optional override; defaults to /models/hf)

echo "[embeddings_init] starting..."

EMB_MODEL="${EMBEDDING_MODEL:-}"
RERANKER_MODEL_ID="${RERANKER_MODEL:-}"

if [ -z "$EMB_MODEL" ] && [ -z "$RERANKER_MODEL_ID" ]; then
  echo "[embeddings_init] No models configured; nothing to do."
  exit 0
fi

# Hardcode Hugging Face cache root (unless caller overrides HF_HOME)
HF_HOME_DIR="${HF_HOME:-/models/hf}"
export HF_HOME="$HF_HOME_DIR"
HF_HUB_DIR="${HF_HOME_DIR%/}/hub"
mkdir -p "$HF_HUB_DIR"

echo "[embeddings_init] Using HF_HOME=${HF_HOME} (hub=$HF_HUB_DIR)"

echo "[embeddings_init] Installing huggingface_hub (with hf_transfer support)..."
python -m pip install -q "huggingface_hub[hf_transfer]"

for pair in "embedding:${EMB_MODEL}" "reranker:${RERANKER_MODEL_ID}"; do
  role="${pair%%:*}"
  model="${pair#*:}"

  if [ -z "$model" ]; then
    echo "[${role}_init] Model id not set; skipping."
    continue
  fi

  echo "[${role}_init] Preparing cache for ${model} ..."
  TARGET_ROLE="$role" TARGET_MODEL="$model" python - <<'PY'
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download

role = os.environ["TARGET_ROLE"]
model_id = os.environ["TARGET_MODEL"]
token = os.environ.get("HF_TOKEN")
cache_root = Path(os.environ.get("HF_HOME", "/models/hf")) / "hub"
prefix = f"[{role}_init]"

WEIGHT_PATTERNS = (
    "pytorch_model.bin",
    "pytorch_model-*.bin",
    "model.safetensors",
    "*.safetensors",
    "tf_model.h5",
    "model.ckpt.index",
    "flax_model.msgpack",
)


def has_model_weights(snapshot: Path) -> bool:
    for pattern in WEIGHT_PATTERNS:
        if "*" in pattern:
            if any(snapshot.glob(pattern)):
                return True
        else:
            if (snapshot / pattern).exists():
                return True
    return False


def cleanup_incomplete(repo_root: Path) -> None:
    for path in list(repo_root.rglob("*.incomplete")):
        try:
            path.unlink()
            print(f"{prefix} Removed stale partial blob: {path}")
        except OSError as exc:
            print(f"{prefix} Warning: failed to remove {path}: {exc}")
    snapshots_dir = repo_root / "snapshots"
    if snapshots_dir.is_dir():
        for snapshot_dir in list(snapshots_dir.iterdir()):
            if snapshot_dir.is_dir() and not has_model_weights(snapshot_dir):
                try:
                    shutil.rmtree(snapshot_dir)
                    print(f"{prefix} Removed weightless snapshot: {snapshot_dir}")
                except OSError as exc:
                    print(f"{prefix} Warning: failed to remove snapshot {snapshot_dir}: {exc}")


def fetch_snapshot(force_download: bool) -> Path:
    return Path(
        snapshot_download(
            repo_id=model_id,
            token=token,
            cache_dir=str(cache_root),
            force_download=force_download,
            resume_download=not force_download,
            local_files_only=not force_download,
        )
    )


print(f"{prefix} Checking local cache for {model_id} ...")
try:
    snapshot_path = fetch_snapshot(force_download=False)
    print(f"{prefix} Cache candidate located at: {snapshot_path}")
except Exception:
    print(f"{prefix} Cache fetch failed in local-only mode; trying online download ...")
    snapshot_path = fetch_snapshot(force_download=True)
    print(f"{prefix} Downloaded cache to: {snapshot_path}")

repo_root = snapshot_path.parent.parent
needs_refresh = False

if not has_model_weights(snapshot_path):
    print(f"{prefix} Snapshot {snapshot_path} is missing model weights.")
    needs_refresh = True

if any(repo_root.rglob("*.incomplete")):
    print(f"{prefix} Detected incomplete blobs under {repo_root}; will refresh cache.")
    needs_refresh = True

if needs_refresh:
    cleanup_incomplete(repo_root)
    snapshot_path = fetch_snapshot(force_download=True)
    print(f"{prefix} Refetched snapshot to {snapshot_path}")

if not has_model_weights(snapshot_path):
    raise SystemExit(
        f"{prefix} ERROR: snapshot at {snapshot_path} still lacks model weights after redownload."
        " Check network connectivity or HF_TOKEN permissions."
    )

print(f"{prefix} Ready: {snapshot_path}")
PY
done

echo "[embeddings_init] Done. Current cache tree:"
ls -lR "$HF_HUB_DIR" | awk 'NR<300' || true
echo "[embeddings_init] completed."
