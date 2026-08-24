#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
#  nebius.sh — drive the Nebius H100 from your Mac: validate, bootstrap, train.
#
#  Quick start:
#    ./nebius.sh doctor                      # check VM + HF reachability
#    ./nebius.sh bootstrap                   # one-time: set up lerobot on the VM
#    ./nebius.sh train <hf_user>/my_task     # train (default: act, 60k steps)
#    ./nebius.sh logs                         # tail the live training log
#    ./nebius.sh pull                         # copy trained checkpoints back
#
#  Config lives in nebius.env (VM host/user/key, lerobot commit, defaults).
# ═════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ---- locate project root + load config ----
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export ROBOT_ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck disable=SC1091
[ -f "$HERE/nebius.env" ] || { echo "nebius/nebius.env not found — copy nebius.env.example to nebius.env and fill it in."; exit 1; }
source "$HERE/nebius.env"
# HF_USER lives in env.sh, HF_TOKEN in .env
[ -f "$ROBOT_ROOT/env.sh" ] && source "$ROBOT_ROOT/env.sh"
[ -f "$ROBOT_ROOT/.env" ]   && { set -a; source "$ROBOT_ROOT/.env"; set +a; }

SSH_OPTS=(-i "$NB_SSH_KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=30)

c_grn=$'\033[32m'; c_red=$'\033[31m'; c_yel=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'
ok(){ echo "  ${c_grn}✓${c_rst} $*"; }
bad(){ echo "  ${c_red}✗${c_rst} $*"; }
warn(){ echo "  ${c_yel}!${c_rst} $*"; }

# Run a command on the VM (non-interactive).
_ssh(){ ssh "${SSH_OPTS[@]}" -o BatchMode=yes "$NB_USER@$NB_HOST" "$@"; }
# Interactive SSH (allocates a TTY).
_ssh_tty(){ ssh "${SSH_OPTS[@]}" "$NB_USER@$NB_HOST" "$@"; }
# Nebius CLI wrapper.
_nb(){ "$HOME/.nebius/bin/nebius" "$@"; }
# Current public IP of the instance (empty if not RUNNING / unreachable).
_nb_ip(){ _nb compute instance get --id "$NB_INSTANCE_ID" --format json 2>/dev/null | python3 -c "import sys,json;
d=json.load(sys.stdin); n=d.get('status',{}).get('network_interfaces',[]);
print((n[0].get('public_ip_address',{}).get('address','') if n else '').split('/')[0])" 2>/dev/null; }

usage(){ sed -n '2,20p' "$HERE/nebius.sh" | sed 's/^# \{0,1\}//'; }

# ─── doctor: validate everything the training flow depends on ────────────────
cmd_doctor(){
  echo "── Nebius VM ($NB_HOST) ──"
  if nc -z -G 6 "$NB_HOST" 22 2>/dev/null; then ok "TCP 22 open"; else bad "TCP 22 unreachable — is the VM running?"; fi

  # Probe the configured user first, then common fallbacks, to find one that auths.
  local found=""
  for u in "$NB_USER" ubuntu root; do
    if ssh "${SSH_OPTS[@]}" -o BatchMode=yes "$u@$NB_HOST" true 2>/dev/null; then found="$u"; break; fi
  done
  if [ -n "$found" ]; then
    ok "SSH key auth works as '${found}'"
    [ "$found" != "$NB_USER" ] && warn "nebius.env has NB_USER=$NB_USER — change it to '$found'"
    echo "${c_dim}    $(_ssh 'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader' 2>/dev/null | head -1)${c_rst}"
    if _ssh 'test -d ~/robot/.venv' 2>/dev/null; then ok "VM already bootstrapped (~/robot/.venv present)"; else warn "VM not bootstrapped yet — run: ./nebius.sh bootstrap"; fi
  else
    bad "SSH key rejected for all of: $NB_USER ubuntu root"
    echo "${c_dim}    The pubkey the VM expects isn't in ~/.ssh or the project. Fix with:${c_rst}"
    echo "${c_dim}    ./nebius.sh fixkey${c_rst}"
  fi

  echo "── Hugging Face ──"
  if [ -n "${HF_TOKEN:-}" ]; then
    local who; who="$(NO_COLOR=1 conda run -n lerobot hf auth whoami 2>/dev/null | head -1 || true)"
    [ -n "$who" ] && ok "HF token valid ($who)" || bad "HF token set but whoami failed"
  else
    bad "HF_TOKEN not found in $ROBOT_ROOT/.env"
  fi
}

# ─── fixkey: install nebius_ssh.pub onto the VM's authorized_keys ────────────
cmd_fixkey(){
  local pub; pub="$(cat "$NB_SSH_KEY.pub")"
  cat <<EOF
The VM is rejecting every local key, so its authorized_keys needs this line:

$pub

Pick whichever you can do:

 A) Nebius CLI: authenticate once, then add the key to the instance metadata:
      ~/.nebius/bin/nebius profile create        # opens a browser to log in

 B) Nebius web console → your VM → "Web/serial console" (or any shell you
    already have on it), then paste:
      mkdir -p ~/.ssh && echo "$pub" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys

 C) If you have password SSH enabled:
      ssh-copy-id -i "$NB_SSH_KEY.pub" <user>@$NB_HOST

After any of these:  ./nebius.sh doctor
EOF
}

# ─── bootstrap: provision the VM for training ────────────────────────────────
cmd_bootstrap(){
  echo "==> Writing HF creds to VM (~/robot/.env, mode 600, via stdin — not argv)"
  _ssh 'mkdir -p ~/robot && umask 077 && cat > ~/robot/.env' <<EOF
export HF_TOKEN=${HF_TOKEN:-}
export HF_USER=${HF_USER:?HF_USER not set — see env.example.sh}
EOF
  echo "==> Copying bootstrap_vm.sh + train.sh to VM"
  scp "${SSH_OPTS[@]}" "$HERE/bootstrap_vm.sh" "$HERE/train.sh" "$NB_USER@$NB_HOST:~/robot/"
  echo "==> Running bootstrap on the VM (installs lerobot @ $LEROBOT_COMMIT)…"
  _ssh_tty "LEROBOT_REPO='$LEROBOT_REPO' LEROBOT_COMMIT='$LEROBOT_COMMIT' bash ~/robot/bootstrap_vm.sh"
}

# ─── train: launch training in a tmux session on the VM ──────────────────────
cmd_train(){
  local dataset="${1:?Usage: nebius.sh train <dataset_repo_id> [policy] [steps] [batch]}"
  local policy="${2:-$POLICY_TYPE}" steps="${3:-$DEFAULT_STEPS}" batch="${4:-$DEFAULT_BATCH}"
  echo "==> Refreshing train.sh on the VM"
  scp "${SSH_OPTS[@]}" "$HERE/train.sh" "$NB_USER@$NB_HOST:~/robot/train.sh" >/dev/null
  echo "==> Launching in tmux session 'train' (survives disconnect)"
  _ssh "tmux kill-session -t train 2>/dev/null; tmux new-session -d -s train \
    'cd ~/robot && bash train.sh \"$dataset\" \"$policy\" \"$steps\" \"$batch\" 2>&1 | tee ~/robot/train.log'"
  ok "Training started for $dataset ($policy, $steps steps, batch $batch)"
  echo "   Follow it with:  ./nebius.sh logs        (Ctrl-C stops watching, not training)"
  echo "   Attach shell:    ./nebius.sh attach"
}

cmd_logs(){ _ssh_tty 'tail -n 40 -f ~/robot/train.log'; }
cmd_attach(){ _ssh_tty 'tmux attach -t train'; }
cmd_status(){ _ssh 'echo "── tmux ──"; tmux ls 2>/dev/null || echo "(no sessions)"; echo "── gpu ──"; nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader'; }
cmd_ssh(){ _ssh_tty "$@"; }

# ─── pull: copy trained checkpoints back to ./outputs ────────────────────────
cmd_pull(){
  local job="${1:-}"
  mkdir -p "$ROBOT_ROOT/outputs/train"
  echo "==> rsync ~/robot/outputs/train/${job} → outputs/train/"
  rsync -avz --progress -e "ssh ${SSH_OPTS[*]}" \
    "$NB_USER@$NB_HOST:~/robot/outputs/train/${job}" "$ROBOT_ROOT/outputs/train/"
}

# ─── VM lifecycle (save money: stop the H100 when idle) ──────────────────────
cmd_stop(){ echo "==> Stopping $NB_INSTANCE_ID (billing pauses once STOPPED)…"; _nb compute instance stop --id "$NB_INSTANCE_ID"; ok "stop requested"; }

cmd_start(){
  echo "==> Starting ${NB_INSTANCE_ID}"; _nb compute instance start --id "$NB_INSTANCE_ID"
  echo -n "   waiting for RUNNING"
  for _ in $(seq 1 30); do
    local st; st="$(_nb compute instance get --id "$NB_INSTANCE_ID" --format json 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',{}).get('state',''))" 2>/dev/null || true)"
    [ "$st" = "RUNNING" ] && { echo " ✓"; break; }
    echo -n "."; sleep 6
  done
  cmd_refresh_ip
}

# Sync NB_HOST (nebius.env) + HostName (~/.ssh/config) to the VM's live public IP.
cmd_refresh_ip(){
  local ip; ip="$(_nb_ip)"
  if [ -z "$ip" ]; then bad "couldn't read a public IP (is the VM RUNNING?)"; return 1; fi
  if [ "$ip" = "$NB_HOST" ]; then ok "public IP unchanged ($ip)"; return 0; fi
  sed -i '' "s#^export NB_HOST=.*#export NB_HOST=$ip#" "$HERE/nebius.env"
  awk -v ip="$ip" '/^Host nebius-h100$/{b=1} b&&/^[[:space:]]*HostName/{sub(/HostName.*/,"HostName "ip);b=0} {print}' \
    "$HOME/.ssh/config" > "$HOME/.ssh/config.tmp" && mv "$HOME/.ssh/config.tmp" "$HOME/.ssh/config"
  ok "public IP updated: $NB_HOST → $ip  (nebius.env + ~/.ssh/config)"
}

case "${1:-}" in
  doctor|check)  cmd_doctor ;;
  stop)          cmd_stop ;;
  start)         cmd_start ;;
  refresh-ip)    cmd_refresh_ip ;;
  fixkey)        cmd_fixkey ;;
  bootstrap)     cmd_bootstrap ;;
  train)         shift; cmd_train "$@" ;;
  logs)          cmd_logs ;;
  attach)        cmd_attach ;;
  status)        cmd_status ;;
  pull)          shift; cmd_pull "$@" ;;
  ssh)           shift; cmd_ssh "$@" ;;
  ""|help|-h|--help) usage ;;
  *) echo "Unknown command: $1"; echo; usage; exit 1 ;;
esac
