# Copy to env.sh and fill in your values. env.sh is gitignored.
# Find the ports with:  ls /dev/tty.usbmodem*   (unplug/replug to spot which is which)
export ROBOT_PORT=/dev/tty.usbmodemXXXXXXXX     # follower arm
export TELEOP_PORT=/dev/tty.usbmodemYYYYYYYY    # leader arm
export ROBOT_ID=my_robot                        # names of your lerobot calibration files
export TELEOP_ID=my_teleop
export CAMERA_GRIPPER=0                         # OpenCV indices; check with scripts/camprobe.py
export CAMERA_EXTERNAL=1
export HF_USER=your-hf-username
# HF_TOKEN goes in .env (also gitignored):  echo 'HF_TOKEN=hf_...' > .env
