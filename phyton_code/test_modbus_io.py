#!/usr/bin/env python3

from pymodbus.client import ModbusSerialClient

PORT = "/dev/ttyUSB0"
BAUD = 19200

client = ModbusSerialClient(
    port=PORT,
    baudrate=BAUD,
    parity="N",
    stopbits=1,
    timeout=1
)

if not client.connect():
    print("❌ Modbus connect failed")
    exit(1)

print("✅ Connected to Modbus")

# -----------------------------
# TEST ID2 – PT100
# -----------------------------
print("\n--- Reading PT100 (ID2) ---")

rr = client.read_holding_registers(0, 8, device_id=2)

if not rr.isError():
    print("RAW:", rr.registers)

    temps = []
    for r in rr.registers:
        if r >= 0x8000:
            r -= 0x10000
        temps.append(r / 10.0)

    print("Scaled °C:", temps)
else:
    print("❌ Error reading PT100")

# -----------------------------
# TEST ID3 – 4–20 mA
# -----------------------------
print("\n--- Reading Current Loop (ID3) ---")

rr = client.read_input_registers(0, 8, device_id=3)

if not rr.isError():
    print("RAW:", rr.registers)

    currents = [r / 1000.0 for r in rr.registers]
    print("Scaled mA:", currents)
else:
    print("❌ Error reading Current Loop")

client.close()