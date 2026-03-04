from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port="/dev/ttyUSB0",
    baudrate=19200,
    parity="N",
    stopbits=1,
    timeout=1
)

client.connect()

print("Trying holding...")
rr = client.read_holding_registers(address=0, count=8, device_id=3)
print(rr)

print("Trying input...")
rr = client.read_input_registers(address=0, count=8, device_id=3)
print(rr)

client.close()
