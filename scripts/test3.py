import time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

# Isolation test for MOTOR 3 (elbow_flex). Moves ONLY motor 3, prints commanded vs actual.
PORT = '/dev/tty.usbmodem5B3D0433471'
bus = FeetechMotorsBus(port=PORT, motors={'elbow': Motor(3, 'sts3215', MotorNormMode.DEGREES)})
bus.connect()
p0 = bus.read('Present_Position', 'elbow', normalize=False)
print('motor 3 start position:', p0)
bus.write('Operating_Mode', 'elbow', OperatingMode.POSITION.value, normalize=False)
bus.write('Goal_Velocity', 'elbow', 200, normalize=False)   # slow
bus.enable_torque('elbow')
for tgt in (p0 + 200, p0 - 200, p0):
    tgt = max(100, min(3995, tgt))
    bus.write('Goal_Position', 'elbow', tgt, normalize=False)
    time.sleep(1.3)
    actual = bus.read('Present_Position', 'elbow', normalize=False)
    moved = abs(actual - p0) > 30
    print(f'commanded {tgt:5d} -> actual {actual:5d}  {"MOVED" if abs(actual-tgt)<80 else "DID NOT REACH"}')
bus.disable_torque('elbow')
bus.disconnect()
print('done - if actual never changed, motor 3 is faulted/disconnected (power-cycle the arm)')
