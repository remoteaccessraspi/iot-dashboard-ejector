from pathlib import Path
import yaml

# --- robust pymodbus imports (rôzne verzie) ---
try:
    from pymodbus.client import ModbusSerialClient
except Exception:
    from pymodbus.client.sync import ModbusSerialClient  # staršie verzie

def load_settings() -> dict:
    # modbus_test_t1_i1.py je v /home/pi/apps/iot_dashboard
    base = Path(__file__).resolve().parent
    path = base / "config" / "settings.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _call_with_fallback(fn, address: int, count: int, unit_id: int):
    # Podpory naprieč pymodbus verziami:
    # - keyword: unit / slave / device_id
    # - pozične: (address, count, unit)
    tries = [
        ((), {"address": address, "count": count, "device_id": unit_id}),
        ((), {"address": address, "count": count, "unit": unit_id}),
        ((), {"address": address, "count": count, "slave": unit_id}),
        ((address, count, unit_id), {}),
        ((address, count), {"unit": unit_id}),
        ((address, count), {"slave": unit_id}),
    ]
    last = None
    for args, kwargs in tries:
        try:
            if args:
                return fn(*args, **kwargs)
            return fn(**kwargs)
        except TypeError as e:
            last = e
    raise last

def read_regs(client, function: str, address: int, count: int, unit_id: int):
    if function == "holding_registers":
        return _call_with_fallback(client.read_holding_registers, address, count, unit_id)
    if function == "input_registers":
        return _call_with_fallback(client.read_input_registers, address, count, unit_id)
    raise ValueError(f"Unsupported function: {function}")

def decode_int16_list(regs, signed: bool, scale: float):
    out = []
    for v in regs:
        if signed and v >= 0x8000:
            v = v - 0x10000
        out.append(v * float(scale))
    return out

def main():
    cfg = load_settings()["modbus"]

    client = ModbusSerialClient(
        port=cfg["port"],
        baudrate=cfg["baudrate"],
        bytesize=cfg["bytesize"],
        parity=cfg["parity"],
        stopbits=cfg["stopbits"],
        timeout=cfg["timeout_sec"],
    )

    if not client.connect():
        raise RuntimeError(f"Modbus connect failed: {cfg['port']}")

    try:
        # Temperature block
        t_unit = cfg["slaves"]["temperature_slave_id"]
        t_cfg = cfg["registers"]["temperature"]
        rr_t = read_regs(client, t_cfg["function"], t_cfg["address"], t_cfg["count"], t_unit)
        if hasattr(rr_t, "isError") and rr_t.isError():
            raise RuntimeError(f"Temp read error: {rr_t}")

        temps_raw = getattr(rr_t, "registers", None)
        if temps_raw is None:
            raise RuntimeError(f"Temp response missing registers: {rr_t}")

        temps = decode_int16_list(temps_raw, t_cfg.get("signed", False), t_cfg["scale"])

        # Current block
        i_unit = cfg["slaves"]["current_slave_id"]
        i_cfg = cfg["registers"]["current_loop"]
        rr_i = read_regs(client, i_cfg["function"], i_cfg["address"], i_cfg["count"], i_unit)
        if hasattr(rr_i, "isError") and rr_i.isError():
            raise RuntimeError(f"Current read error: {rr_i}")

        currents_raw = getattr(rr_i, "registers", None)
        if currents_raw is None:
            raise RuntimeError(f"Current response missing registers: {rr_i}")

        currents = decode_int16_list(currents_raw, i_cfg.get("signed", False), i_cfg["scale"])

        print("Temps raw:", temps_raw)
        print("Temps °C :", [round(x, 2) for x in temps])
        print("Curr raw :", currents_raw)
        print("Curr mA  :", [round(x, 3) for x in currents])

    finally:
        client.close()

if __name__ == "__main__":
    main()