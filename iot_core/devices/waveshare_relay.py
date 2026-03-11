from iot_core.devices.base_device import BaseDevice


class WaveshareRelay(BaseDevice):

    def __init__(self, slave_id):
        super().__init__(slave_id)

    def execute(self, client, db_conn):

        # --------------------------------------------------
        # 1️⃣ READ DESIRED RELAY STATES FROM DATABASE
        # --------------------------------------------------

        relay_states = {f"r{i+1}": 0 for i in range(8)}

        try:

            with db_conn.cursor() as cur:

                cur.execute("""
                    SELECT name, state
                    FROM relay_state
                    WHERE name IN ('r1','r2','r3','r4','r5','r6','r7','r8')
                """)

                rows = cur.fetchall()

                for row in rows:

                    # PyMySQL vracia tuple ('r1',1)
                    name = row[0]
                    state = row[1]

                    relay_states[name] = int(state)

        except Exception as e:

            print("Waveshare DB error (relay read):", e)
            return

        # --------------------------------------------------
        # 2️⃣ READ CURRENT RELAY STATES FROM DEVICE
        # --------------------------------------------------

        try:

            rr = client.read_coils(
                address=0,
                count=8,
                device_id=self.slave_id
            )

        except Exception as e:

            print("Waveshare Modbus read failed:", e)
            return

        if rr.isError():

            print("Waveshare read error:", rr)
            return

        current_states = {}

        for i in range(8):

            relay_name = f"r{i+1}"

            current_states[relay_name] = 1 if rr.bits[i] else 0

        # --------------------------------------------------
        # 3️⃣ DETECT RELAY CHANGES
        # --------------------------------------------------

        coils_to_write = []

        for i in range(8):

            relay_name = f"r{i+1}"

            desired = relay_states.get(relay_name, 0)
            current = current_states.get(relay_name, 0)

            if desired != current:

                coils_to_write.append((i, desired))

        # --------------------------------------------------
        # 4️⃣ WRITE RELAYS
        # --------------------------------------------------

        for address, value in coils_to_write:

            try:

                wr = client.write_coil(
                    address=address,
                    value=bool(value),
                    device_id=self.slave_id
                )

                if wr.isError():

                    print(f"Waveshare write error relay {address+1}")
                    continue

                relay_name = f"r{address+1}"

                print(
                    f"Waveshare {relay_name}: "
                    f"{current_states[relay_name]} -> {value}"
                )

                current_states[relay_name] = value

            except Exception as e:

                print(f"Waveshare write failed relay {address+1}:", e)

        # --------------------------------------------------
        # 5️⃣ STORE SNAPSHOT TO DATABASE
        # --------------------------------------------------

        try:

            snapshot = [current_states[f"r{i+1}"] for i in range(8)]

            with db_conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO relay
                    (r1,r2,r3,r4,r5,r6,r7,r8)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, tuple(snapshot))

            db_conn.commit()

        except Exception as e:

            print("Waveshare DB error (snapshot):", e)