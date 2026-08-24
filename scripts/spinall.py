import time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

PORT = '/dev/tty.usbmodem5B3D0433471'
for mid in range(1, 6):
    bus = FeetechMotorsBus(port=PORT,
        motors={'m': Motor(mid, 'sts3215', MotorNormMode.DEGREES)})
    bus.connect()
    bus.write('Operating_Mode', 'm', OperatingMode.POSITION.value, normalize=False)
    bus.enable_torque('m')
    p = bus.read('Present_Position', 'm', normalize=False)
    print(f'motor {mid} start {p}')
    bus.write('Goal_Position', 'm', p + 500, normalize=False); time.sleep(1)
    bus.write('Goal_Position', 'm', p - 500, normalize=False); time.sleep(1)
    bus.write('Goal_Position', 'm', p, normalize=False); time.sleep(1)
    bus.disable_torque('m'); bus.disconnect()
    print(f'motor {mid} done')
    time.sleep(0.5)
print('all done')
