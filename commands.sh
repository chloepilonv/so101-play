#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
#  SO-101 → Hugging Face → Nebius H100 : end-to-end cheat-sheet
#  These are copy-paste blocks, not a script to run top-to-bottom.
# ═════════════════════════════════════════════════════════════════════════════

cd "$(git rev-parse --show-toplevel)"   # repo root
conda activate lerobot
set -a; source .env; source env.sh; set +a     # HF_TOKEN, HF_USER, ports, camera indices

# ── 1. RECORD a dataset locally (arm + leader connected) ─────────────────────
#   keys during recording:  → next   ← redo   ESC finish & upload
lerobot-record \
  --robot.type=so101_follower --robot.port="$ROBOT_PORT"  --robot.id="$ROBOT_ID" \
  --teleop.type=so101_leader  --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id="$HF_USER/my_task" \
  --dataset.single_task="<one-sentence task description>" \
  --dataset.num_episodes=50 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=10 \
  --display_data=true
#   ↑ ESC uploads it to https://huggingface.co/datasets/$HF_USER/my_task

# ── 1b. (IF NEEDED) upload a recorded dataset to HF robustly ─────────────────
#   lerobot-record auto-uploads on ESC. But if you recorded without it, or the
#   upload stalled (Xet + flaky uplink), use this — it watchdog-resumes the
#   upload AND creates the version tag lerobot-train needs:
#   ./upload_to_hf.sh ~/.cache/huggingface/lerobot/$HF_USER/my_task_<timestamp> $HF_USER/my_task

# ── 2. INSPECT it before training (always) ───────────────────────────────────
#   https://huggingface.co/spaces/lerobot/visualize_dataset  → paste  $HF_USER/my_task

# ── 3. TRAIN on the Nebius H100 ──────────────────────────────────────────────
cd nebius
./nebius.sh doctor                          # validate VM + HF are reachable
./nebius.sh bootstrap                       # one-time only: set up lerobot on the VM
./nebius.sh train "$HF_USER/my_task"        # act, 60k steps, batch 64 (override: <policy> <steps> <batch>)
./nebius.sh logs                            # watch it train
./nebius.sh pull                            # bring checkpoints back to ../outputs/train/
#   trained policy is auto-pushed to  https://huggingface.co/$HF_USER/act_my_task

# ── 4. EVAL on the real robot ────────────────────────────────────────────────
cd ..
lerobot-record \
  --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id="$HF_USER/eval_my_task" \
  --dataset.single_task="<same task description>" \
  --dataset.num_episodes=10 \
  --policy.path="$HF_USER/act_my_task"

# ── 5. ROLL OUT a policy on the arm (no recording) ──────────────────────────
lerobot-rollout --strategy.type=base --policy.path="$HF_USER/act_my_task" \
  --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30}}" \
  --task="<same task description>" --duration=20
#   camera keys must match the dataset; --duration ≈ one episode length (ACT has no "stop" action)

# More detail: nebius/README.md  ·  README.md
