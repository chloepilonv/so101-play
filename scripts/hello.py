import time
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig

cfg = SO101FollowerConfig(port='/dev/tty.usbmodem5B3D0433471', id='follower')
robot = SOFollower(cfg)
robot.connect()
obs = robot.get_observation()
home = {k: v for k, v in obs.items() if k.endswith('.pos')}
print('home:', home)

def send(d):
    robot.send_action(d); time.sleep(1.2)

for _ in range(3):
    a = dict(home); a['wrist_flex.pos'] = home['wrist_flex.pos'] + 15; send(a)
    a = dict(home); a['wrist_flex.pos'] = home['wrist_flex.pos'] - 15; send(a)
send(home)
robot.disconnect()
print('done')
