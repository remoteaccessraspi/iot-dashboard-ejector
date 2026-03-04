import time

from iot_core.core.config import load_config
from iot_core.db.connection import get_connection
from iot_core.modbus.client import create_client

from iot_core.devices.opta_pid import OptaPID
from iot_core.devices.temperature import TemperatureDevice
from iot_core.devices.current_loop import CurrentLoopDevice


def main():

    cfg = load_config()
    modbus_cfg = cfg["modbus"]

    db_conn = get_connection()
    client = create_client()

    timeout = modbus_cfg.get("timeout_sec", 1)

    if hasattr(client, "timeout"):
        client.timeout = timeout
    if hasattr(client, "retries"):
        client.retries = 0

    if hasattr(client, "connect"):
        if not client.connect():
            print("Initial connect failed")
        else:
            print("Connected to Modbus")

    # 🔥 Slave IDs zo settings.yaml
    slaves_cfg = modbus_cfg["slaves"]

    opta = OptaPID(
        slave_id=slaves_cfg["opta_slave_id"]
    )

    temperature = TemperatureDevice(
        slave_id=slaves_cfg["temperature_slave_id"],
        reg_cfg=modbus_cfg["registers"]["temperature"]
    )

    current_loop = CurrentLoopDevice(
        slave_id=slaves_cfg["current_slave_id"],
        reg_cfg=modbus_cfg["registers"]["current_loop"]
    )

    devices = [
         opta,          # ID1 – function 04
        temperature,   # ID2 – function 03
        current_loop   # ID3 – function 03
    ]

    print(
        f"Modbus Master started "
        f"(ID1={slaves_cfg['opta_slave_id']}, "
        f"ID2={slaves_cfg['temperature_slave_id']}, "
        f"ID3={slaves_cfg['current_slave_id']})"
    )

    PERIOD = 5.0
    FRAME_DELAY = 0.1  # 100 ms medzi slave

    while True:

        cycle_start = time.monotonic()

        # Reconnect ak treba
        if hasattr(client, "connected") and not client.connected:
            print("Reconnecting...")
            try:
                client.connect()
            except Exception as e:
                print("Reconnect failed:", e)
                time.sleep(1)
                continue

        # 🔁 Deterministický round-robin
        for device in devices:

            try:
                device.execute(client, db_conn)

            except Exception as e:
                print(f"{device.__class__.__name__} error:", e)

                try:
                    client.close()
                except Exception:
                    pass

                time.sleep(0.2)

                try:
                    client.connect()
                except Exception as e2:
                    print("Reconnect after error failed:", e2)

            time.sleep(FRAME_DELAY)

        # Stabilná perióda cyklu
        elapsed = time.monotonic() - cycle_start
        sleep_time = PERIOD - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            print("Cycle overrun:", round(-sleep_time, 3), "s")


if __name__ == "__main__":
    main()