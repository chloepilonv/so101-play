"""compare23.py — read motor 2 (works) vs motor 3 (trips) torque/overload/limit settings side by side.

A difference on a torque or protection register would explain why m3 trips while m2 doesn't —
and it'd be a setting (fixable), not a dead motor.
"""
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = '/dev/tty.usbmodem5B3D0433471'
REGS = [
    'Max_Torque_Limit', 'Torque_Limit', 'Overload_Torque', 'Protective_Torque',
    'Protection_Current', 'Protection_Time', 'Over_Current_Protection_Time',
    'Minimum_Startup_Force', 'Acceleration', 'Maximum_Acceleration', 'Maximum_Velocity_Limit',
    'Min_Position_Limit', 'Max_Position_Limit', 'Max_Temperature_Limit',
    'Max_Voltage_Limit', 'Min_Voltage_Limit',
]

bus = FeetechMotorsBus(port=PORT, motors={
    'm2': Motor(2, 'sts3215', MotorNormMode.DEGREES),
    'm3': Motor(3, 'sts3215', MotorNormMode.DEGREES),
})
bus.connect(handshake=False)

print(f"{'register':28s} {'m2 (works)':>12s} {'m3 (trips)':>12s}   diff?")
print('-' * 70)
for reg in REGS:
    try:
        v2 = bus.read(reg, 'm2', normalize=False)
        v3 = bus.read(reg, 'm3', normalize=False)
        flag = '  <-- DIFFERENT' if v2 != v3 else ''
        print(f"{reg:28s} {str(v2):>12s} {str(v3):>12s}{flag}")
    except Exception as e:
        print(f"{reg:28s} {'n/a':>12s} {'n/a':>12s}   ({type(e).__name__})")
bus.disconnect()
print("\nLook for '<-- DIFFERENT' on a Torque/Overload/Protection register: that'd be the cause.")
