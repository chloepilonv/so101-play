#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# train.sh — run ON the Nebius H100 VM (from ~/robot) to train an SO-101 policy.
# `nebius.sh train ...` scp's this here and launches it inside a tmux session so
# it survives disconnects. You can also run it by hand after SSH-ing in.
#
# Usage:
#   ./train.sh <dataset_repo_id> [policy] [steps] [batch]
# Example:
#   ./train.sh <hf_user>/pick_place_cube act 60000 64
#
# The trained policy is pushed to the Hub as  <HF_USER>/<policy>_<dataset-name>.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DATASET_REPO_ID="${1:?Usage: train.sh <dataset_repo_id> [policy] [steps] [batch]}"
POLICY="${2:-act}"
STEPS="${3:-60000}"
BATCH="${4:-64}"

ROBOT_DIR="$HOME/robot"
cd "$ROBOT_DIR"

# Load HF creds (HF_TOKEN / HF_USER) written by `nebius.sh bootstrap`.
if [ -f "$ROBOT_DIR/.env" ]; then set -a; source "$ROBOT_DIR/.env"; set +a; fi
HF_USER="${HF_USER:?HF_USER not set — check ~/robot/.env}"

# shellcheck disable=SC1091
source "$ROBOT_DIR/.venv/bin/activate"

TASK_SLUG="${DATASET_REPO_ID##*/}"
JOB="${POLICY}_${TASK_SLUG}"
OUT="outputs/train/${JOB}"

echo "────────────────────────────────────────────────────────────"
echo " dataset : $DATASET_REPO_ID"
echo " policy  : $POLICY   steps: $STEPS   batch: $BATCH"
echo " output  : $OUT"
echo " push to : ${HF_USER}/${JOB}"
echo "────────────────────────────────────────────────────────────"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader || true
echo "────────────────────────────────────────────────────────────"

# VLAs (SmolVLA) gain a lot from unfreezing the vision encoder — LeRobot ships it
# frozen; unfreezing is where the generalization improvement comes from.
EXTRA_ARGS=()
if [ "$POLICY" = "smolvla" ]; then
  EXTRA_ARGS+=(--policy.freeze_vision_encoder=false --policy.train_expert_only=false)
fi

lerobot-train \
  --dataset.repo_id="$DATASET_REPO_ID" \
  --policy.type="$POLICY" \
  --policy.device=cuda \
  "${EXTRA_ARGS[@]}" \
  --output_dir="$OUT" \
  --job_name="$JOB" \
  --batch_size="$BATCH" \
  --steps="$STEPS" \
  --save_freq=5000 \
  --log_freq=200 \
  --wandb.enable=false \
  --policy.push_to_hub=true \
  --policy.repo_id="${HF_USER}/${JOB}"

echo ""
echo "✅ Training done. Checkpoints in $OUT/checkpoints  ·  policy pushed to ${HF_USER}/${JOB}"

