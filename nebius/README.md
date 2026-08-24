# Train SO-101 policies on the Nebius H100

Everything for going from **a dataset on the Hub → a trained policy** on the
Nebius H100 VM. You record datasets locally (on the Mac, with the arm) and push
them to Hugging Face; this box pulls them and trains.

```
nebius/
  nebius.env        # your config (copy nebius.env.example): VM host/user/key, lerobot commit, defaults
  nebius.sh         # ← the one command you run. Subcommands below.
  bootstrap_vm.sh   # runs on the VM (one-time setup). Called by `nebius.sh bootstrap`.
  train.sh          # runs on the VM (the lerobot-train call). Called by `nebius.sh train`.
```

## The flow

```bash
cd nebius

./nebius.sh doctor                       # 1. validate VM + HF reachability
./nebius.sh bootstrap                    # 2. one-time: install lerobot on the VM
./nebius.sh train <hf_user>/<dataset>      # 3. train (default: act, 60k steps, batch 64)
./nebius.sh logs                         # 4. watch the live log (Ctrl-C = stop watching)
./nebius.sh pull                         # 5. copy checkpoints back to ../outputs/train/
```

The trained policy is also pushed to the Hub automatically as
`<hf_user>/<policy>_<dataset-name>`.

## Commands

| Command | What it does |
| --- | --- |
| `./nebius.sh doctor` | Check TCP:22, SSH key auth (probes the right user), GPU, and HF token. |
| `./nebius.sh fixkey` | If SSH is rejected, prints the ways to add your key to the VM. |
| `./nebius.sh bootstrap` | Installs system deps, uv, a py3.12 venv, and lerobot @ the pinned commit; logs into HF. Idempotent. |
| `./nebius.sh train <repo_id> [policy] [steps] [batch]` | Launches training in a `tmux` session (survives disconnect). |
| `./nebius.sh logs` | `tail -f` the training log. |
| `./nebius.sh attach` | Attach to the tmux training session. |
| `./nebius.sh status` | tmux sessions + `nvidia-smi` on the VM. |
| `./nebius.sh pull [job]` | rsync trained checkpoints back into `../outputs/train/`. |
| `./nebius.sh ssh [cmd]` | Open a shell on the VM (or run one command). |
| `./nebius.sh stop` | Stop the H100 (billing pauses) when you're not training. |
| `./nebius.sh start` | Start it again, wait for RUNNING, and auto-refresh the IP. |
| `./nebius.sh refresh-ip` | Re-read the VM's public IP and update `nebius.env` + `~/.ssh/config`. |

## Training knobs

Defaults live in `nebius.env` (`POLICY_TYPE`, `DEFAULT_STEPS`, `DEFAULT_BATCH`)
and can be overridden per run:

```bash
./nebius.sh train <hf_user>/pick_place            # act, 60k steps, batch 64
./nebius.sh train <hf_user>/pick_place act 40000 96
./nebius.sh train <hf_user>/pick_place smolvla 50000 32   # needs the [smolvla] extra — see below
```

Step-count guidance: ACT single-task ~30k–80k;
think in **epochs** (5–10 over the dataset), not raw steps. On an 80GB H100, ACT
is tiny — batch 64+ is comfortable.

### Other policies

The VM installs base lerobot (covers **ACT** and **diffusion**). For a VLA, add
its extra once on the VM:

```bash
./nebius.sh ssh 'cd ~/robot && source .venv/bin/activate && uv pip install -e "./lerobot[smolvla]"'
# then: ./nebius.sh train <hf_user>/<dataset> smolvla
```

## Version pinning — why we clone instead of pip install

Your local lerobot is **0.5.2** (commit `b06ad408` on the HF repo), which is *not*
published on PyPI. Datasets are format-tied to the lerobot version, so the VM
clones the repo and checks out that exact commit (`LEROBOT_COMMIT` in
`nebius.env`) to match. Bump it there if you upgrade locally.

## Notes

- **HF token** is read from `../.env` and written to the VM at `~/robot/.env`
  (mode 600, sent over SSH stdin — never on a command line). Consider rotating it
  if this VM is shared.
- **SSH config**: `refresh-ip` also updates a `Host nebius-h100` entry in `~/.ssh/config` if present.
- **Nebius CLI** (`~/.nebius/bin/nebius`, authenticated with `nebius profile create`)
  drives the `stop`/`start`/`refresh-ip` commands above.
- **Money:** the H100 bills whenever it's RUNNING. `./nebius.sh stop` when idle,
  `./nebius.sh start` when you're ready to train — `start` auto-updates the IP if
  Nebius reassigned it, so nothing else breaks.
