#!/usr/bin/env python3

import time
from datetime import datetime, time as dtime
import yaml
import pymysql
from pathlib import Path


# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"


# --------------------------------------------------
# LOAD CONFIG
# --------------------------------------------------

def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------
# DB
# --------------------------------------------------

def db_connect(cfg):
    db = cfg["database"]
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["name"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# --------------------------------------------------
# TIME CHECK
# --------------------------------------------------

def parse_time_safe(tstr):

    if tstr == "24:00":
        return dtime(23, 59, 59)

    return datetime.strptime(tstr, "%H:%M").time()


def time_ok(rule_time, now):

    if not rule_time:
        return True

    t_from = parse_time_safe(rule_time["from"])
    t_to   = parse_time_safe(rule_time["to"])

    now_t = now.time()

    # normálny interval
    if t_from <= t_to:
        return t_from <= now_t <= t_to

    # interval cez polnoc
    return now_t >= t_from or now_t <= t_to


# --------------------------------------------------
# CONDITIONS
# --------------------------------------------------

def cond_ok(cond, data):

    val = data.get(cond["source"])

    if val is None:
        return False

    if "min" in cond and val < cond["min"]:
        return False

    if "max" in cond and val > cond["max"]:
        return False

    return True


# --------------------------------------------------
# LOAD LAST VALUES
# --------------------------------------------------

def read_latest(conn):

    out = {}

    with conn.cursor() as cur:

        cur.execute("SELECT * FROM temperature ORDER BY id DESC LIMIT 1")
        t = cur.fetchone() or {}

        cur.execute("SELECT * FROM conversion_table ORDER BY id DESC LIMIT 1")
        p = cur.fetchone() or {}

    for i in range(1, 9):
        out[f"t{i}"] = t.get(f"t{i}")
        out[f"p{i}"] = p.get(f"p{i}")

    return out


# --------------------------------------------------
# UPDATE RELAY
# --------------------------------------------------

def update_relay(conn, name, state):

    with conn.cursor() as cur:

        cur.execute("""
            REPLACE INTO relay_state(name,state,source)
            VALUES (%s,%s,'auto')
        """, (name, int(state)))


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def main():

    cfg = load_cfg()
    conn = db_connect(cfg)

    last_mtime = 0
    relay_cfg = {}

    print("Relay engine started")

    while True:

        now = datetime.now()

        # -----------------------------
        # CONFIG RELOAD (smart)
        # -----------------------------

        try:
            mtime = SETTINGS_PATH.stat().st_mtime

            if mtime != last_mtime:
                cfg = load_cfg()
                relay_cfg = cfg.get("relay", {}).get("control", {})
                last_mtime = mtime
                print("Config reloaded")

        except Exception as e:
            print("Config reload error:", e)

        # -----------------------------
        # DB RECONNECT
        # -----------------------------

        try:
            conn.ping(reconnect=True)
        except Exception:
            print("DB reconnect")
            conn = db_connect(cfg)

        # -----------------------------
        # LOAD DATA
        # -----------------------------

        data = read_latest(conn)

        # -----------------------------
        # RELAY EVALUATION
        # -----------------------------

        for name, rcfg in relay_cfg.items():

            if rcfg.get("mode") != "auto":
                continue

            logic = rcfg.get("logic", "OR")
            rules = rcfg.get("rules", [])

            final = False if logic == "OR" else True

            for rule in rules:

                t_ok = time_ok(rule.get("time"), now)
                c_ok = all(cond_ok(c, data) for c in rule.get("conditions", []))

                active = t_ok and c_ok

                # DEBUG (môžeš vypnúť neskôr)
                print(f"{name} | t_ok={t_ok} c_ok={c_ok} -> {active}")

                if logic == "OR":
                    final = final or active
                else:
                    final = final and active

            print(f"{name} => FINAL: {final}")

            update_relay(conn, name, final)

        time.sleep(1)


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()