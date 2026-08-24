#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# bootstrap_vm.sh — run ONCE on the Nebius H100 VM to prepare it for training.
# Normally you don't call this by hand; `nebius.sh bootstrap` scp's it here and
# runs it for you. Idempotent: safe to re-run.
#
# Env it expects (nebius.sh passes these):
#   LEROBOT_REPO, LEROBOT_COMMIT   — which lerobot to install
# It reads HF creds from ~/robot/.env (written by `nebius.sh bootstrap`).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

LEROBOT_REPO="${LEROBOT_REPO:-https://github.com/huggingface/lerobot.git}"
LEROBOT_COMMIT="${LEROBOT_COMMIT:-}"
ROBOT_DIR="$HOME/robot"

echo "==> [1/6] System packages (git, git-lfs, ffmpeg, build tools)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y -q
sudo apt-get install -y -q git git-lfs ffmpeg build-essential python3-dev tmux rsync
git lfs install

echo "==> [2/6] uv (Python/venv manager)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "==> [3/6] Clone LeRobot @ ${LEROBOT_COMMIT:-main}"
mkdir -p "$ROBOT_DIR"
if [ ! -d "$ROBOT_DIR/lerobot/.git" ]; then
  git clone "$LEROBOT_REPO" "$ROBOT_DIR/lerobot"
fi
cd "$ROBOT_DIR/lerobot"
git fetch --all --quiet || true
if [ -n "$LEROBOT_COMMIT" ]; then
  git checkout --quiet "$LEROBOT_COMMIT"
fi
echo "    lerobot at: $(git rev-parse --short HEAD)"

echo "==> [4/6] Python 3.12 venv + lerobot[training] (CUDA torch pulled automatically on Linux)"
cd "$ROBOT_DIR"
[ -d .venv ] || uv venv --python 3.12 .venv
# shellcheck disable=SC1091
source .venv/bin/activate
# [training] pulls the dataset stack (datasets, pyarrow, torchcodec/av) + accelerate
# + wandb — everything lerobot-train needs. ACT/diffusion policies are in base.
uv pip install --python "$ROBOT_DIR/.venv/bin/python" -e "$ROBOT_DIR/lerobot[training]"

echo "==> [5/6] Verify GPU is visible to torch"
python - <<'PY'
import torch
ok = torch.cuda.is_available()
print(f"    torch {torch.__version__} | cuda_available={ok}")
if ok:
    print(f"    device: {torch.cuda.get_device_name(0)}")
    print(f"    capability: {torch.cuda.get_device_capability(0)}")
else:
    raise SystemExit("!! torch cannot see the GPU — check the NVIDIA driver on the VM.")
PY

echo "==> [6/6] Hugging Face auth"
if [ -f "$ROBOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  set -a; source "$ROBOT_DIR/.env"; set +a
fi
if [ -n "${HF_TOKEN:-}" ]; then
  hf auth login --token "$HF_TOKEN" --add-to-git-credential >/dev/null 2>&1 || true
  echo -n "    logged in as: "; NO_COLOR=1 hf auth whoami | head -1
else
  echo "    !! HF_TOKEN not found in ~/robot/.env — run 'hf auth login' manually."
fi

echo ""
echo "✅ Bootstrap complete. Train with:  nebius.sh train <dataset_repo_id>"
