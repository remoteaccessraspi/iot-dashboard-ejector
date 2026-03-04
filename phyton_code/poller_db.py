#!/usr/bin/env python3
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
import pymysql

# pymodbus import (rôzne verzie)
try:
    from pymodbus.client import ModbusSerialClient
except Exception:
    from pymodbus.client.sync import ModbusSerialClient  # staršie verzie


SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "settings.yaml"


def load_cfg() -> dict:
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Missing settings: {SETTINGS_PATH}")
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


def _call_with_fallback(fn, address: int, count: int, unit_id: int):
    """
    pymodbus má rozdielne API podľa verzie:
      - keyword: unit / slave / device_id
      - alebo pozične: (address, count, unit)
    Skúsime všetky bežné varianty.
    """
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


def decode_scaled(regs, signed: bool, scale: float):
    out = []
    for v in regs:
        if signed and v >= 0x8000:
            v = v - 0x10000
        out.append(v * float(scale))
    return out


def normalize_invalid(values, invalid=-999.0, eps=1e-9):
    # -999.0 -> None (NULL v DB)
    out = []
    for v in values:
        if v is None:
            out.append(None)
        elif abs(v - invalid) < eps:
            out.append(None)
        else:
            out.append(v)
    return out


def db_connect(db: dict):
    """
    Podporí aj DB na Tailscale IP.
    """
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["name"],
        autocommit=True,
        connect_timeout=int(db.get("connect_timeout_sec", 5)),
        charset="utf8mb4",
    )


def main():
    cfg = load_cfg()

    # --- config sections ---
    m = cfg["modbus"]
    db = cfg["database"]
    polling = cfg.get("polling", {})
    interval = int(polling.get("modbus_interval_sec", 5))

    # --- Modbus client ---
    client = ModbusSerialClient(
        port=m["port"],
        baudrate=int(m["baudrate"]),
        bytesize=int(m.get("bytesize", 8)),
        parity=str(m.get("parity", "N")),
        stopbits=int(m.get("stopbits", 1)),
        timeout=float(m.get("timeout_sec", 1.5)),
    )

    if not client.connect():
        raise RuntimeError(f"Modbus connect failed: {m['port']}")

    # --- DB connect ---
    conn = db_connect(db)

    try:
        while True:
            # UTC ISO timestamp (MariaDB TIMESTAMP vie prijať)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            # -------- Temps --------
            t_unit = int(m["slaves"]["temperature_slave_id"])
            t_cfg = m["registers"]["temperature"]
            rr_t = read_regs(client, t_cfg["function"], int(t_cfg["address"]), int(t_cfg["count"]), t_unit)

            if hasattr(rr_t, "isError") and rr_t.isError():
                print("Temp read error:", rr_t)
                time.sleep(interval)
                continue

            temps_raw = getattr(rr_t, "registers", None)
            if temps_raw is None:
                print("Temp response missing registers:", rr_t)
                time.sleep(interval)
                continue

            temps = decode_scaled(
                temps_raw,
                signed=bool(t_cfg.get("signed", False)),
                scale=float(t_cfg["scale"]),
            )
            temps = normalize_invalid(temps, invalid=-999.0)

            # -------- Currents --------
            i_unit = int(m["slaves"]["current_slave_id"])
            i_cfg = m["registers"]["current_loop"]
            rr_i = read_regs(client, i_cfg["function"], int(i_cfg["address"]), int(i_cfg["count"]), i_unit)

            if hasattr(rr_i, "isError") and rr_i.isError():
                print("Current read error:", rr_i)
                time.sleep(interval)
                continue

            currents_raw = getattr(rr_i, "registers", None)
            if currents_raw is None:
                print("Current response missing registers:", rr_i)
                time.sleep(interval)
                continue

            currents = decode_scaled(
                currents_raw,
                signed=bool(i_cfg.get("signed", False)),
                scale=float(i_cfg["scale"]),
            )

            # -------- DB INSERT --------
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO temperature
                      (ts, t1, t2, t3, t4, t5, t6, t7, t8)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (ts, *temps),
                )
                cur.execute(
                    """
                    INSERT INTO current_loop
                      (ts, i1, i2, i3, i4, i5, i6, i7, i8)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (ts, *currents),
                )

            print("OK", ts, "T1=", temps[0], "I8=", currents[7])
            time.sleep(interval)

    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
