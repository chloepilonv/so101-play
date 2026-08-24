from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
m = {f'm{i}': Motor(i,'sts3215',MotorNormMode.DEGREES) for i in range(1,6)}
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471', motors=m)
bus.connect(handshake=False)
for k in m:
    try: bus.disable_torque(k)
    except: pass
bus.disconnect()
print('torque off - joints should move freely now')
