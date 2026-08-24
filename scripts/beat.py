import time
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

PORT = '/dev/tty.usbmodem5B3D0433471'
BPM = 72
beat = 60.0 / BPM

bus = FeetechMotorsBus(port=PORT,
    motors={'m': Motor(5, 'sts3215', MotorNormMode.DEGREES)})
bus.connect()
bus.write('Operating_Mode', 'm', OperatingMode.POSITION.value, normalize=False)
bus.write('Goal_Velocity', 'm', 600, normalize=False)
bus.enable_torque('m')
p = bus.read('Present_Position', 'm', normalize=False)
print('start', p, '- Ctrl-C to stop')

D = 120
i = 0
try:
    while True:
        tgt = p + (D if i % 2 == 0 else -D)
        bus.write('Goal_Position', 'm', max(100, min(3995, tgt)), normalize=False)
        time.sleep(beat)
        i += 1
except KeyboardInterrupt:
    print('\nstopping...')
finally:
    bus.write('Goal_Position', 'm', p, normalize=False); time.sleep(1)
    bus.disable_torque('m'); bus.disconnect()
    print('done')
