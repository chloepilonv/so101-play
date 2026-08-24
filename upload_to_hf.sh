#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# upload_to_hf.sh — robustly push a local LeRobot dataset to the Hub.
# Handles two things a plain `hf upload` does not:
#   1. Flaky uplink → Xet stalls. We watchdog-kill stalls and let Xet RESUME
#      (already-uploaded chunks are skipped server-side) until all files land.
#   2. Raw `hf upload` doesn't create the version tag lerobot-train needs. We
#      read codebase_version from meta/info.json and create that tag.
#
# Usage:
#   ./upload_to_hf.sh <local_dataset_dir> [repo_id]
# Example:
#   ./upload_to_hf.sh ~/.cache/huggingface/lerobot/<hf_user>/pick_place_20260713_1200 <hf_user>/pick_place
# If repo_id is omitted, it's HF_USER/<basename-without-timestamp>.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")"
set -a; [ -f .env ] && source .env; [ -f env.sh ] && source env.sh; set +a
export HF_HUB_DISABLE_XET=0   # Xet = chunked + resumable (what makes retries work)

PY=python3   # run with the lerobot conda env active
HF=hf

FOLDER="${1:?Usage: upload_to_hf.sh <local_dataset_dir> [repo_id]}"
FOLDER="${FOLDER%/}"
BASE="$(basename "$FOLDER")"
REPO="${2:-${HF_USER:?set HF_USER}/${BASE%_20*}}"   # strip _<timestamp> suffix if present

[ -f "$FOLDER/meta/info.json" ] || { echo "!! $FOLDER/meta/info.json not found — is this a LeRobot dataset dir?"; exit 1; }
echo "Uploading: $FOLDER"
echo "     → repo: $REPO (dataset)"

# List of files that must exist on the Hub (everything except the local .cache).
mapfile -t NEED < <(cd "$FOLDER" && find . -type f -not -path './.cache/*' | sed 's#^\./##')

is_complete() {
  HF_TOKEN="$HF_TOKEN" REPO="$REPO" $PY - "${NEED[@]}" <<'PY'
import os, sys
from huggingface_hub import HfApi
need = set(sys.argv[1:])
api = HfApi(token=os.environ["HF_TOKEN"])
try:
    files = set(api.list_repo_files(os.environ["REPO"], repo_type="dataset"))
except Exception:
    sys.exit(1)
sys.exit(0 if need <= files else 1)
PY
}

for attempt in $(seq 1 30); do
  if is_complete; then echo "✓ all files present (before attempt $attempt)"; break; fi
  echo "──── upload attempt $attempt  $(date +%H:%M:%S) ────"
  log=$(mktemp)
  $HF upload "$REPO" "$FOLDER" --repo-type dataset >"$log" 2>&1 &
  pid=$!; last=""; stale=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 10
    cur=$(grep -oE '[0-9.]+[KMGB]+ transferred' "$log" | tail -1)
    echo "  [$(date +%H:%M:%S)] ${cur:-<checking/hashing>}"
    if [ "$cur" = "$last" ]; then stale=$((stale+1)); else stale=0; last="$cur"; fi
    if [ "$stale" -ge 3 ]; then
      echo "  stalled ~30s → killing to force Xet resume"
      kill -TERM "$pid" 2>/dev/null; sleep 2; kill -KILL "$pid" 2>/dev/null
    fi
  done
  wait "$pid" 2>/dev/null; tail -1 "$log"; rm -f "$log"
  is_complete && { echo "✓ upload complete (attempt $attempt)"; break; }
  sleep 3
done

is_complete || { echo "!! upload did not complete after retries"; exit 1; }

# Create the LeRobot version tag (codebase_version from info.json) if missing.
echo "──── ensuring version tag ────"
HF_TOKEN="$HF_TOKEN" REPO="$REPO" INFO="$FOLDER/meta/info.json" $PY - <<'PY'
import os, json
from huggingface_hub import HfApi
ver = json.load(open(os.environ["INFO"]))["codebase_version"]   # e.g. "v3.0"
api = HfApi(token=os.environ["HF_TOKEN"]); repo = os.environ["REPO"]
tags = [t.name for t in api.list_repo_refs(repo, repo_type="dataset").tags]
if ver in tags:
    print(f"✓ tag {ver} already present")
else:
    api.create_tag(repo, tag=ver, repo_type="dataset")
    print(f"✓ created tag {ver}")
PY

echo ""
echo "✅ Done. Dataset ready to train:  https://huggingface.co/datasets/$REPO"
echo "   Train it:  cd nebius && ./nebius.sh train $REPO"
