from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
m = {f'm{i}': Motor(i,'sts3215',MotorNormMode.DEGREES) for i in range(1,7)}  # 1-5, no gripper yet
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471', motors=m)
bus.connect()
for k in m: print(k, bus.read('Present_Position', k, normalize=False))
bus.disconnect()
print('all found')
