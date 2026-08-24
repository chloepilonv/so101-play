import sys, time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

mid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471',
    motors={'m': Motor(mid, 'sts3215', MotorNormMode.DEGREES)})
bus.connect()
bus.write('Operating_Mode', 'm', OperatingMode.POSITION.value, normalize=False)
bus.enable_torque('m')
p = bus.read('Present_Position', 'm', normalize=False)
print(f'motor {mid} start', p)
bus.write('Goal_Position', 'm', p + 500, normalize=False); time.sleep(1)
bus.write('Goal_Position', 'm', p - 500, normalize=False); time.sleep(1)
bus.write('Goal_Position', 'm', p, normalize=False); time.sleep(1)
bus.disable_torque('m'); bus.disconnect()
print('done')

