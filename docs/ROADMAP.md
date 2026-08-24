# SO-101 in Simulation — Roadmap

_Created 2026-07-13. Companion to `NOTES.md` (real-robot + BC training so far). This file
covers the **simulation** direction: two ways to use Isaac Sim / Isaac Lab to train the SO-101._

---

## Where we're coming from

So far everything has been **behavior cloning (BC / imitation)** on *real* teleop data:
record demos on the arm → `upload_to_hf.sh` → train **ACT** / **SmolVLA** on the Nebius H100 →
run on the robot. No simulator, no reward, no sim-to-real gap — the policy just imitates
demonstrations. See `NOTES.md`.

Now we want to bring **simulation** into the loop. There are two distinct approaches. They are
**not** competitors — they solve different problems and can even be combined. This roadmap tracks both.

| | **Approach 1 — Synthetic Data** | **Approach 2 — RL Policy** |
|---|---|---|
| **What the robot learns from** | Demonstrations (like now, but sim-generated & varied) | Reward + trial-and-error in sim |
| **Learning paradigm** | Imitation / BC — *same as ACT/SmolVLA today* | Reinforcement learning (PPO) |
| **Simulator role** | A **data factory** (render varied demos) | A **training gym** (millions of attempts) |
| **Output** | A dataset → train ACT/SmolVLA/GR00T as usual | A trained control policy (net) |
| **Sim-to-real gap** | Crossed via domain randomization in the renders | Crossed via DR + (usually) teacher→student distill |
| **Main labor** | Getting demos / trajectories into sim, DR tuning | Reward engineering + distillation + sim-to-real |
| **Best suited to** | Tabletop manipulation (our pick-place) | Dynamic / contact-rich control; also viable for manip |
| **Reuses our BC stack?** | ✅ fully (LeRobot train pipeline unchanged) | ❌ new stack (Isaac Lab + rsl_rl/skrl PPO) |

**Shared reality — hardware:** Isaac Sim is CUDA/Linux-only. The **Mac cannot run it**. Both
approaches run on the **Nebius H100** (headless) or any RTX/L40/Blackwell/Ada box. The workshop
Docker images target Ubuntu ≥22.04 + NVIDIA Container Toolkit.

**Shared asset base — the cloned `Sim-to-Real-SO-101-Workshop`** already gives us, for *both* paths:
- `assets/so101.py` — `ArticulationCfg` on `SO-ARM101-USD.usd`, **actuator stiffness/damping hand-tuned per joint** (normally the painful part)
- `assets/usd/` — vial, rack, tray, mat, lightbox; 20+ HDRIs for lighting DR
- `tasks/` — `ManagerBasedRLEnvCfg` scene, `ActionsCfg` (`JointPositionActionCfg`), `ObservationsCfg`, `VialsToRackTerminationsCfg` (a `success` term), a `contact_grasp` `ContactSensorCfg`, and DR event configs (`VialsToRackEventDRCfg`)
- `gr00t_client/` + `utils/lerobot_*` — recording, dataset push, and GR00T inference plumbing

---

## Approach 1 — Synthetic Data (sim as a data factory)

**Idea:** Use Isaac to *generate* a large, **varied**, domain-randomized demonstration dataset,
then train ACT / SmolVLA / GR00T on it with the **exact BC pipeline we already run**. This is
literally what the NVIDIA workshop is built to do (teleop → record → imitation with GR00T).

**Why it's attractive for us:** zero new learning paradigm, no reward engineering, no
distillation. It plugs straight into `lerobot-train`. Variety (object scattered across the
workspace, lighting, textures) comes for free from domain randomization instead of hand-recording
hundreds of real episodes.

### Pipeline
```
Isaac scene + SO-101  →  generate trajectories  →  render with DR  →  LeRobot dataset
   →  upload_to_hf.sh  →  lerobot-train (ACT / SmolVLA / GR00T)  →  deploy on real arm
```

### How trajectories get generated (pick one, roughly increasing effort)
1. **Teleop in sim** — drive the sim arm (workshop's `lerobot_agent`), record like real demos. Simplest; still human-in-the-loop.
2. **Scripted / waypoint policies** — hand-code a pick-place motion (IK to grasp pose → close → lift → place). Cheap to fan out across randomized object positions.
3. **Trajectory replay + DR** — take one good motion, replay it under thousands of randomized scenes/lighting/object poses → massive varied dataset from little human effort.
4. **(Cross-over) a trained RL policy as the demonstrator** — Approach 2's policy generates perfect demos → back into BC. This is the hybrid link between the two paths.

### Milestones
- [ ] **1.0** Get the workshop teleop+sim Docker container running on the H100 (headless / streamed). Confirm `list_envs` shows the `Lerobot-So101-*` envs.
- [ ] **1.1** Reproduce the workshop's record → `lerobot_push_dataset` path for the vial→rack task; get one sim dataset onto HF.
- [ ] **1.2** Adapt the scene/task to *our* task ("white object in blue circle") — swap USD assets, set the success condition. (Or just adopt vial→rack as the sim task.)
- [ ] **1.3** Turn on domain randomization (`VialsToRackEventDRCfg`) and generate a **varied** dataset (object position first, then lighting/texture).
- [ ] **1.4** Train ACT + SmolVLA on the sim dataset via the existing Nebius flow; compare.
- [ ] **1.5** Deploy on the real arm — measure the sim-to-real gap. Iterate DR to close it.

---

## Approach 2 — RL Policy (sim as a training gym)  ← the one we're most curious about

**Idea:** Define a **reward**, spawn thousands of SO-101s in parallel in Isaac Lab, and train a
control policy with **PPO** until it solves the task by trial-and-error. Then transfer that policy
to the real arm ("put it on the robot").

**Why it's a real project (be honest with ourselves):**
- **Reward engineering is the work.** Sparse "vial in rack" won't train from scratch → shape it:
  reach (distance hand→object) → grasp (contact) → lift (height) → place (distance→goal) → success bonus.
  We already have the *sensors* for this: `contact_grasp` and the `success` termination exist.
- **Privileged-state → vision gap.** RL trains fastest on exact object pose from sim ground truth,
  which the real camera can't give. Standard fix: train a **state-based "teacher,"** then
  **distill to a vision "student"** that uses only camera + proprioception. Two stages.
- **Sim-to-real** still has to be crossed with DR + actuator/latency modeling. The workshop's DR
  configs and the tuned actuators in `so101.py` are the starting point.

**What's already scaffolded vs. what's missing:** the env is `ManagerBasedRLEnvCfg` with scene,
robot, actions, observations, terminations, contact sensor, and DR **already present**. The
**missing pieces to make it RL are basically two:**
1. a **`RewardsCfg`** (reward terms) — *does not exist yet in the repo*
2. an **RL runner + agent config** (rsl_rl / skrl PPO) wired to the env, replacing the teleop agent

### Pipeline
```
Isaac Lab env (+ RewardsCfg)  →  PPO across N parallel envs (state-based teacher)
   →  distill to vision student (teacher-student)  →  harden with domain randomization
   →  export policy  →  run on real SO-101
```

### RL library choice (decision needed — see Open Questions)
- **`rsl_rl`** — minimal, fast PPO; the Isaac Lab default for locomotion. Simplest to start.
- **`skrl`** — more algorithms, clean Isaac Lab integration.
- **`rl_games`** — high-throughput, used in many Isaac manipulation examples.
Recommendation: start with **rsl_rl PPO**, state-based, single task.

### Milestones
- [ ] **2.0** Stand up **Isaac Lab** (not just the workshop) on the H100 — verify a stock example trains (e.g. a shipped manipulation or reach task) so the RL loop is known-good.
- [ ] **2.1** Register an **SO-101 reach task**: reuse `SO101_CFG` + scene, action = joint position, obs = proprioception + target. Simplest possible reward (distance to a target pose). Get PPO to *move the arm to a point*. This is the "hello world" that proves the whole stack.
- [ ] **2.2** Author a **`RewardsCfg` for pick-place** (reach→grasp→lift→place→success), reusing `contact_grasp` + the `success` term. Train a **state-based teacher** (privileged object pose).
- [ ] **2.3** **Distill teacher → vision student** (camera + proprio only). This is the policy that could actually run on the real arm.
- [ ] **2.4** **Sim-to-real hardening** — crank DR (`VialsToRackEventDRCfg` + actuator/latency randomization), close the loop on the real robot.
- [ ] **2.5** **Export + deploy** the student policy on the real SO-101. Decide the runtime (ONNX / TorchScript, or bridge into a LeRobot-style rollout).

---

## Hybrid / crossover ideas (once both paths exist)
- **RL policy → demonstrator for BC** (Approach 2 feeds Approach 1): a solved RL policy generates flawless, infinitely-varied demos to train a deployable ACT/SmolVLA.
- **BC → RL fine-tune**: warm-start RL from our existing BC policy (residual RL) so PPO doesn't explore from scratch.
- **RL on the *real* robot instead of sim** — LeRobot's **HIL-SERL** (human-in-the-loop sample-efficient RL): RL with no sim-to-real gap at all. Different tool, same "RL" goal; parked here as an alternative to Approach 2.

---

## Open questions / decisions to make
1. **Task**: adopt the workshop's **vial→rack**, or port our **"white object in blue circle"** into sim? (Vial→rack is zero-asset-work and fully scaffolded.)
2. **Compute**: run Isaac on the **Nebius H100**  vs. a cheaper dedicated RTX box? Isaac + parallel RL wants the GPU running for a while — cost matters.
3. **Approach 2 RL library**: rsl_rl (start here) vs skrl vs rl_games.
4. **Deployment runtime for an RL policy**: how does an Isaac-trained net run on the arm — reuse `lerobot-rollout`, or a standalone inference script? (BC uses `lerobot-rollout`; RL policy I/O differs.)
5. **Sequencing**: do **Approach 1** first (lower risk, reuses our stack, real dataset payoff) and treat **Approach 2** as the deeper build? Or start **2.1 (RL reach)** in parallel as the learning exercise.

---

## Suggested first moves
- **Approach 1**: milestone **1.0** — get the workshop sim container running on the H100.
- **Approach 2**: milestone **2.0 → 2.1** — Isaac Lab up, then an SO-101 **reach** task with PPO. Smallest end-to-end RL loop; everything else builds on it.

_Refs: `Sim-to-Real-SO-101-Workshop/` (assets + envs), `NOTES.md` (BC + Nebius), `nebius/README.md` (H100 ops)._
