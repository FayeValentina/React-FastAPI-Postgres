#!/usr/bin/env sh
set -eu
# Best-effort enable pipefail if supported by the shell
set -o pipefail 2>/dev/null || true

# This script downloads a spaCy model wheel to /models if not present.
# Env vars supported (provided by compose):
# - SPACY_MODEL_URL: wheel URL to fetch (required)

echo "[spacy_init] starting..."

MODEL_URL="${SPACY_MODEL_URL:-}"

if [ -z "$MODEL_URL" ]; then
  echo "[spacy_init] SPACY_MODEL_URL is not set." >&2
  exit 1
fi

echo "[spacy_init] Ensuring curl is available ..."
if ! command -v curl >/dev/null 2>&1; then
  echo "[spacy_init] Installing curl ..."
  apt-get update -y >/dev/null 2>&1 \
    && apt-get install -y --no-install-recommends curl ca-certificates >/dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*
fi

mkdir -p /models

echo "[spacy_init] Preparing cleanup list ..."
MODEL_FILE="$(basename "$MODEL_URL")"
KEEPS=" $MODEL_FILE "

# Cleanup: remove old spaCy wheels not in keep list, and any leftover .part* files
echo "[spacy_init] Cleaning up stale spaCy wheels and .part files in /models ..."
for f in /models/*.whl; do
  [ -e "$f" ] || break
  bn="$(basename "$f")"
  case " $KEEPS " in
    *" $bn "*)
      echo "[spacy_init] keep: $bn"
      ;;
    *)
      echo "[spacy_init] remove: $bn"
      rm -f -- "$f" || true
      ;;
  esac
done
# Remove leftover partials and temporary files (older runs)
find /models -maxdepth 1 -type f \( -name "*.part*" -o -name "*.tmp*" \) -print -delete 2>/dev/null || true

download_one() {
  url="$1"
  [ -z "$url" ] && return 0
  fname="$(basename "$url")"
  dst="/models/${fname}"
  part="${dst}.part"
  if [ -f "$dst" ]; then
    echo "[spacy_init] Already present: $dst"
    return 0
  fi
  tries=5
  echo "[spacy_init] Downloading $fname ..."
  i=1
  while [ "$i" -le "$tries" ]; do
    echo "[spacy_init] Attempt ${i}/${tries} ..."
    if curl -fL --retry 5 --retry-delay 10 --retry-connrefused -C - -o "$part" "$url"; then
      mv -f "$part" "$dst"
      echo "[spacy_init] Downloaded: $dst"
      return 0
    else
      echo "[spacy_init] Curl failed (attempt $i). Will retry."
      sleep 10
    fi
    i=$((i+1))
  done
  echo "[spacy_init] Failed to download $fname after $tries attempts." >&2
  return 1
}

ok=0
download_one "$MODEL_URL" || ok=1

ls -lh /models || true
if [ "$ok" -ne 0 ]; then
  echo "[spacy_init] completed with errors." >&2
  exit 1
fi
echo "[spacy_init] done."
