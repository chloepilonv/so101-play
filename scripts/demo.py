import time
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig

cfg = SO101FollowerConfig(port='/dev/tty.usbmodem5B3D0433471', id='follower')
robot = SOFollower(cfg)
robot.connect()
obs = robot.get_observation()
home = {k: v for k, v in obs.items() if k.endswith('.pos')}
print('home:', {k: round(v,1) for k,v in home.items()})

def send(changes, settle=1.3):
    a = dict(home); a.update(changes); robot.send_action(a); time.sleep(settle)

try:
    # safe, low-gravity-load joints get bigger moves:
    send({'shoulder_pan.pos': home['shoulder_pan.pos'] + 30})   # base swivel
    send({'shoulder_pan.pos': home['shoulder_pan.pos'] - 30})
    send({'shoulder_pan.pos': home['shoulder_pan.pos']})

    send({'wrist_roll.pos': home['wrist_roll.pos'] + 40})       # wrist twist
    send({'wrist_roll.pos': home['wrist_roll.pos'] - 40})
    send({'wrist_roll.pos': home['wrist_roll.pos']})

    send({'wrist_flex.pos': home['wrist_flex.pos'] + 20})       # wrist nod
    send({'wrist_flex.pos': home['wrist_flex.pos'] - 20})
    send({'wrist_flex.pos': home['wrist_flex.pos']})

    send({'gripper.pos': home['gripper.pos'] + 30})             # gripper open/close
    send({'gripper.pos': home['gripper.pos']})

    # heavy joints (2,3): tiny, brief only
    send({'elbow_flex.pos': home['elbow_flex.pos'] - 10})
    send({'elbow_flex.pos': home['elbow_flex.pos']})

    send(home)  # return
finally:
    time.sleep(0.5)
    robot.disconnect()
    print('done')
