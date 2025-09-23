#!/usr/bin/env sh
set -eu
# Best-effort enable pipefail if supported by the shell
set -o pipefail 2>/dev/null || true

# This script downloads Hugging Face GGUF models into /models.
# It supports downloading the primary chat model (HF_*) and an optional
# classifier model (CLASSIFIER_*). Any other *.gguf files in /models will be
# removed to avoid mixing incompatible artifacts.

echo "[llm_init] starting..."

python -m pip install -q "huggingface_hub[hf_transfer]"

echo "[llm_init] preparing downloads..."

python - <<'PY'
import os
import shutil
from pathlib import Path
from typing import List

from huggingface_hub import hf_hub_download


def build_target(label: str, repo_var: str, filename_var: str, revision_var: str, token_var: str) -> dict | None:
    filename = os.getenv(filename_var)
    if not filename:
        print(f"[llm_init] {label} filename not set; skipping.")
        return None

    repo = os.getenv(repo_var)
    if not repo:
        raise SystemExit(f"[llm_init] {label} repo variable {repo_var} is not set; cannot download {filename}.")

    revision = os.getenv(revision_var, "main")
    token = os.getenv(token_var) or os.getenv("HF_TOKEN")
    return {
        "label": label,
        "repo": repo,
        "filename": filename,
        "revision": revision,
        "token": token,
    }


def ensure_models(targets: List[dict]) -> None:
    models_dir = Path("/models")
    models_dir.mkdir(parents=True, exist_ok=True)

    target_files = {target["filename"] for target in targets}
    for path in models_dir.glob("*.gguf"):
        if path.name in target_files:
            print(f"[llm_init] keep existing model: {path.name}")
        else:
            print(f"[llm_init] remove stale model: {path.name}")
            path.unlink(missing_ok=True)

    for target in targets:
        dst = models_dir / target["filename"]
        if dst.exists():
            print(f"[llm_init] Model already present: {dst}")
            continue

        print(
            f"[llm_init] Downloading {target['filename']} from {target['repo']} "
            f"(rev={target['revision']}) for {target['label']}..."
        )
        downloaded = hf_hub_download(
            repo_id=target["repo"],
            filename=target["filename"],
            revision=target["revision"],
            token=target["token"],
        )
        dst.parent.mkdir(parents=True, exist_ok=True)
        downloaded_path = Path(downloaded)
        if downloaded_path.resolve() != dst.resolve():
            shutil.copy2(downloaded_path, dst)
            print(f"[llm_init] Copied to {dst}")
        else:
            print(f"[llm_init] Downloaded to {dst}")

    print("[llm_init] Models available:")
    for path in sorted(models_dir.glob("*.gguf")):
        print(f" - {path.name}")


def main() -> None:
    targets: List[dict] = []

    primary = build_target("primary", "CHAT_REPO_ID", "CHAT_FILENAME", "CHAT_REVISION", "HF_TOKEN")
    if primary:
        targets.append(primary)

    classifier = build_target("classifier", "CLASSIFIER_REPO_ID", "CLASSIFIER_FILENAME", "CLASSIFIER_REVISION", "HF_TOKEN")
    if classifier:
        targets.append(classifier)

    if not targets:
        print("[llm_init] No models requested; exiting.")
        return

    ensure_models(targets)


if __name__ == "__main__":
    main()
PY

ls -lh /models || true
echo "[llm_init] done."
