"""status3.py — read MOTOR 3 (elbow) health: temperature, voltage, load, torque, error status.

Run this RIGHT AFTER a failed move (before power-cycling) to catch an overload/overheat trip.
"""
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = '/dev/tty.usbmodem5B3D0433471'
bus = FeetechMotorsBus(port=PORT, motors={'m3': Motor(3, 'sts3215', MotorNormMode.DEGREES)})
bus.connect(handshake=False)

for reg in ['Present_Position', 'Goal_Position', 'Torque_Enable', 'Status',
            'Present_Temperature', 'Present_Voltage', 'Present_Load', 'Present_Current', 'Moving']:
    try:
        print(f"{reg:20s} = {bus.read(reg, 'm3', normalize=False)}")
    except Exception as e:
        print(f"{reg:20s} = n/a ({type(e).__name__})")
bus.disconnect()
print("\nread: Torque_Enable 0 = torque tripped off (overload).  "
      "Status != 0 = hardware error flag.  Temperature in C (>65 = overheat).")
