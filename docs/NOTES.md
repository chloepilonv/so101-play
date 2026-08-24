# Lessons from the imitation-learning runs

Task: "Put the white object in the blue circle". 30 teleop episodes, 12,702 frames, about 7 minutes,
two cameras (front + wrist). Trained on a Nebius H100 with the scripts in `../nebius/`.

| Policy | Params | Final loss | Notes |
|---|---|---|---|
| ACT | 52M | 0.042 | Trains from scratch, fast. Good first baseline |
| SmolVLA | 403M | 0.013 | Pretrained VLA from Hugging Face, language-conditioned. Vision encoder unfrozen during fine-tuning |

## The big lesson: data variety beats model tuning

ACT completed the task but failed when the object moved by 1 cm. All 30 demos had the object in
roughly the same spot, so the policy memorized one trajectory instead of using the cameras to
locate the object. The fix is to record 30 to 50 more episodes with the object scattered across the
workspace (vary one axis at a time), then retrain. LeRobot's rule: start constrained, confirm it
works, then add diversity.

## Running a policy on the arm

- Camera keys must match the dataset (`front` + `wrist`). Camera placement, calibration id,
  lighting and object must match training. Behavior cloning does not extrapolate.
- "It finishes but keeps moving" is normal: ACT has no stop action and runs for the full
  `--duration`. Set it to about one episode length, or use `--strategy.type=episodic`.
- SO-101 leader→follower teleop is joint-space (direct angle copying), so kinematic
  singularities never come up. They only matter under Cartesian/IK control like `scripts/ik_play.py`.

## Vocabulary

- Dataset size: episodes, frames (timesteps), hours, camera views.
- Training: steps × batch = frames seen = dataset frames × epochs. Think in epochs (5 to 10 over
  the dataset) rather than raw steps.

## Next

1. Compare SmolVLA vs ACT on the arm, first at the trained position, then with the 1 cm shift.
2. Record varied episodes, upload with `upload_to_hf.sh`, retrain.
3. Simulation: see [ROADMAP.md](ROADMAP.md).
