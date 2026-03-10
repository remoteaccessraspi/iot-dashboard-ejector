from iot_core.devices.base_device import BaseDevice
import time


# ==========================================================
# MODBUS TIMING
# ==========================================================

MODBUS_GAP = 0.02        # 20 ms medzi rámcami
READ_WRITE_PAUSE = 0.2   # pauza medzi read a write


# ==========================================================
# READ FALLBACK (pymodbus kompatibilita)
# ==========================================================

def _call_read_with_fallback(fn, address: int, count: int, unit_id: int):

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


# ==========================================================
# WRITE MULTIPLE COILS
# ==========================================================

def _call_write_coils_with_fallback(client, address, values, slave_id):

    try:
        try:
            return client.write_coils(address, values, unit=slave_id)
        except TypeError:
            try:
                return client.write_coils(address, values, slave=slave_id)
            except TypeError:
                try:
                    return client.write_coils(address, values, device_id=slave_id)
                except TypeError:
                    return client.write_coils(address, values, slave_id)
    except Exception as e:
        raise e


# ==========================================================
# WRITE HOLDING REGISTERS
# ==========================================================

def _call_write_with_fallback(client, address, values, slave_id):

    try:
        try:
            return client.write_registers(address, values, unit=slave_id)
        except TypeError:
            try:
                return client.write_registers(address, values, slave=slave_id)
            except TypeError:
                try:
                    return client.write_registers(address, values, device_id=slave_id)
                except TypeError:
                    return client.write_registers(address, values, slave_id)
    except Exception as e:
        raise e


# ==========================================================
# DEVICE CLASS
# ==========================================================

class OptaPID(BaseDevice):

    def __init__(self, slave_id):
        super().__init__(slave_id)

    def execute(self, client, db_conn):

        # ==========================================================
        # 1️⃣ READ INPUT REGISTERS
        # ==========================================================

        try:
            rr = _call_read_with_fallback(
                getattr(client, "read_input_registers"),
                address=0,
                count=5,
                unit_id=self.slave_id
            )
        except Exception as e:
            print("OPTA Modbus read failed:", e)
            return

        if not rr or (hasattr(rr, "isError") and rr.isError()):
            print("OPTA read error:", rr)
            return

        if not hasattr(rr, "registers") or len(rr.registers) != 5:
            print("OPTA invalid response:", rr)
            return

        regs = rr.registers

        # signed conversion
        regs = [(v - 0x10000 if v >= 0x8000 else v) for v in regs]

        feedback = regs[0] / 10.0
        current_duty = regs[1] / 10.0

        try:
            with db_conn.cursor() as cur:

                cur.execute("""
                    REPLACE INTO relay_state(name,state,source)
                    VALUES ('pid_feedback', %s, 'opta')
                """, (feedback,))

                cur.execute("""
                    REPLACE INTO relay_state(name,state,source)
                    VALUES ('pwm_output', %s, 'opta')
                """, (current_duty,))

        except Exception as e:
            print("OPTA DB error (read):", e)

        # ==========================================================
        # PAUZA READ → WRITE
        # ==========================================================

        time.sleep(READ_WRITE_PAUSE)

        # ==========================================================
        # 2️⃣ READ CONTROL PARAMETERS
        # ==========================================================

        params = {}

        try:
            with db_conn.cursor() as cur:

                cur.execute("""
                    SELECT parameter, value
                    FROM control
                    WHERE parameter IN (
                        'pwm_period',
                        'pwm_duty',
                        'pid_t_set',
                        'pid_t_full',
                        'pid_t_move'
                    )
                    ORDER BY ts DESC
                """)

                rows = cur.fetchall()

        except Exception as e:
            print("OPTA DB error (control read):", e)
            return

        for param, value in rows:
            if param not in params:
                params[param] = value

        try:

            pwm_period = int(float(params.get("pwm_period", 0) or 0))
            pwm_duty   = int(float(params.get("pwm_duty", 0) or 0))

            t_set      = float(params.get("pid_t_set", 0) or 0)
            t_full     = int(float(params.get("pid_t_full", 0) or 0))
            t_move     = int(float(params.get("pid_t_move", 0) or 0))

        except Exception as e:
            print("OPTA parameter conversion error:", e)
            return

        t_set_scaled = int(round(t_set * 10))

        values = [
            pwm_period,
            pwm_duty,
            t_set_scaled,
            t_full,
            t_move,
        ]

        # ==========================================================
        # 3️⃣ READ COIL STATES FROM DATABASE
        # ==========================================================

        coil_values = {}

        try:
            with db_conn.cursor() as cur:

                cur.execute("""
                    SELECT name, state
                    FROM relay_state
                    WHERE name IN ('r1','r2')
                """)

                rows = cur.fetchall()

                # tuple unpacking (funguje vždy)
                for name, state in rows:
                    coil_values[name] = state

        except Exception as e:
            print("OPTA DB error (coil read):", e)

        # bezpečný default
        enable_pwm = bool(coil_values.get("r1", 1))
        enable_pid = bool(coil_values.get("r2", 1))

        # ==========================================================
        # 4️⃣ WRITE COILS (FC15)
        # ==========================================================

        try:

            wr_coils = _call_write_coils_with_fallback(
                client,
                address=0,
                values=[enable_pwm, enable_pid],
                slave_id=self.slave_id
            )

            if hasattr(wr_coils, "isError") and wr_coils.isError():
                print("OPTA coil write error:", wr_coils)

        except Exception as e:
            print("OPTA coil write failed:", e)

        time.sleep(MODBUS_GAP)

        # ==========================================================
        # 5️⃣ WRITE HOLDING REGISTERS
        # ==========================================================

        try:

            wr = _call_write_with_fallback(
                client,
                address=0,
                values=values,
                slave_id=self.slave_id
            )

        except Exception as e:
            print("OPTA write failed:", e)
            return

        if hasattr(wr, "isError") and wr.isError():
            print("OPTA write error:", wr)
            return