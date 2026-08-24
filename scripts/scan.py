from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors import Motor, MotorNormMode
bus = FeetechMotorsBus(port='/dev/tty.usbmodem5B3D0433471',
    motors={'m': Motor(1,'sts3215',MotorNormMode.DEGREES)})
bus.connect(handshake=False)
print('IDs on bus:', bus.broadcast_ping())
bus.disconnect()
