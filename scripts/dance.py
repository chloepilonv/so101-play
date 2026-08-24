import time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
m = {f'm{i}': Motor(i,'sts3215',MotorNormMode.DEGREES) for i in range(1,6)}
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471', motors=m)
bus.connect()
start = {k: bus.read('Present_Position', k, normalize=False) for k in m}
for k in m:
    bus.write('Operating_Mode', k, OperatingMode.POSITION.value, normalize=False)
    bus.write('Goal_Velocity', k, 200, normalize=False)  # slow speed cap
    bus.enable_torque(k)

def goto(k, target):
    target = max(100, min(3995, target))   # stay away from 0/4095 wrap
    bus.write('Goal_Position', k, target, normalize=False)

D = 80  # small move, ~7 degrees
for k in m:
    goto(k, start[k]+D); time.sleep(0.4)
for k in m:
    goto(k, start[k]); time.sleep(0.4)
time.sleep(1)
for k in m: bus.disable_torque(k)
bus.disconnect()
print('done')
