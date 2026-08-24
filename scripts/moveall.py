import time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
m = {f'm{i}': Motor(i,'sts3215',MotorNormMode.DEGREES) for i in range(1,6)}
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471', motors=m)
bus.connect()
start = {k: bus.read('Present_Position', k, normalize=False) for k in m}
for k in m:
    bus.write('Operating_Mode', k, OperatingMode.POSITION.value, normalize=False)
    bus.enable_torque(k)
for k in m: bus.write('Goal_Position', k, start[k]+150, normalize=False)
time.sleep(1)
for k in m: bus.write('Goal_Position', k, start[k]-150, normalize=False)
time.sleep(1)
for k in m: bus.write('Goal_Position', k, start[k], normalize=False)
time.sleep(1)
for k in m: bus.disable_torque(k)
bus.disconnect()
print('done')
