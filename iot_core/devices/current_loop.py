from iot_core.devices.base_device import BaseDevice


def _call_with_fallback(fn, address: int, count: int, unit_id: int):
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


def decode_scaled(regs, scale: float):
    return [v * scale for v in regs]


class CurrentLoopDevice(BaseDevice):

    def __init__(self, slave_id, reg_cfg):
        super().__init__(slave_id)
        self.reg_cfg = reg_cfg

    def execute(self, client, db_conn):

        rr = _call_with_fallback(
            getattr(client, f"read_{self.reg_cfg['function']}"),
            address=self.reg_cfg["address"],
            count=self.reg_cfg["count"],
            unit_id=self.slave_id
        )

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("Current read error:", rr)
            return

        regs = rr.registers

        if self.reg_cfg.get("signed", False):
            regs = [(v - 0x10000 if v >= 0x8000 else v) for v in regs]

        currents = [v * self.reg_cfg["scale"] for v in regs]

        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO current_loop
                (ts,i1,i2,i3,i4,i5,i6,i7,i8)
                VALUES (NOW(),%s,%s,%s,%s,%s,%s,%s,%s)
            """, currents)