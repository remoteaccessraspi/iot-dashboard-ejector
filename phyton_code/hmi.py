#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
import pymysql
from flask import Flask, jsonify, render_template, request

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "settings.yaml"


def load_cfg() -> dict:
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))


def db_connect(db: dict):
    return pymysql.connect(
        host=db["host"],
        port=int(db.get("port", 3306)),
        user=db["user"],
        password=db["password"],
        database=db["name"],
        autocommit=True,
        connect_timeout=int(db.get("connect_timeout_sec", 5)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


app = Flask(__name__)

_cfg = load_cfg()
_db_cfg = _cfg["database"]
_hmi_cfg = _cfg.get("hmi", {})
_refresh_ms = int(_hmi_cfg.get("refresh_ms", 2000))

# --------------------------------------------------
# CHANNEL METADATA (names + units)
# --------------------------------------------------

_channels_cfg = _cfg.get("channels", {})

_t_names = [
    _channels_cfg.get(f"t{i}", {}).get("name", f"t{i}")
    for i in range(1, 9)
]

_t_units = [
    _channels_cfg.get(f"t{i}", {}).get("unit", "")
    for i in range(1, 9)
]

_p_names = [
    _channels_cfg.get(f"p{i}", {}).get("name", f"p{i}")
    for i in range(1, 9)
]

_p_units = [
    _channels_cfg.get(f"p{i}", {}).get("unit", "")
    for i in range(1, 9)
]

# --------------------------------------------------
# DB CONNECTION
# --------------------------------------------------

_conn = None


def get_conn():
    global _conn
    try:
        if _conn is None:
            _conn = db_connect(_db_cfg)
        else:
            _conn.ping(reconnect=True)
        return _conn
    except Exception:
        try:
            if _conn:
                _conn.close()
        except Exception:
            pass
        _conn = db_connect(_db_cfg)
        return _conn


# --------------------------------------------------
# INIT DEFAULT CONTROL VALUES
# --------------------------------------------------

def initialize_control_defaults():
    pwm_cfg = _cfg.get("pwm", {})
    pid_cfg = _cfg.get("pid", {})

    defaults = {
        "pwm_period": pwm_cfg.get("period", {}).get("default"),
        "pwm_duty": pwm_cfg.get("duty", {}).get("default"),
        "pid_t_set": pid_cfg.get("t_set", {}).get("default"),
        "pid_t_full": pid_cfg.get("t_full", {}).get("default"),
        "pid_t_move": pid_cfg.get("t_move", {}).get("default"),
    }

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            for param, value in defaults.items():
                if value is None:
                    continue

                cur.execute(
                    "SELECT 1 FROM control WHERE parameter=%s LIMIT 1",
                    (param,)
                )

                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO control (parameter,value,source) VALUES (%s,%s,'init')",
                        (param, str(value))
                    )
                    print(f"[INIT] Inserted default for {param} = {value}")

    except Exception as e:
        print(f"[INIT ERROR] {e}")


# --------------------------------------------------
# DB HELPERS
# --------------------------------------------------

def _table_has_column(table: str, column: str) -> bool:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
            LIMIT 1
            """,
            (_db_cfg["name"], table, column),
        )
        return cur.fetchone() is not None


def _latest_row(table: str):
    try:
        conn = get_conn()
        order_col = "id" if _table_has_column(table, "id") else "ts"
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM `{table}` ORDER BY `{order_col}` DESC LIMIT 1"
            )
            return cur.fetchone()
    except Exception:
        return None


# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.get("/")
def index():
    return render_template("monitor.html", refresh_ms=_refresh_ms)


@app.get("/control")
def control_page():
    return render_template(
        "control.html",
        pwm=_cfg.get("pwm", {}),
        pid=_cfg.get("pid", {})
    )


@app.get("/api/latest")
def api_latest():

    try:
        trow = _latest_row("temperature")
        irow = _latest_row("current_loop")
        prow = _latest_row("conversion_table")
        db_status = "OK"
    except Exception:
        db_status = "ERR"
        trow = irow = prow = None

    def pick(row, keys):
        if not row:
            return [None] * len(keys)
        return [row.get(k) for k in keys]

    data = {
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "refresh_ms": _refresh_ms,
        "db_status": db_status,
        "t": pick(trow, [f"t{i}" for i in range(1, 9)]),
        "i": pick(irow, [f"i{i}" for i in range(1, 9)]),
        "p": pick(prow, [f"p{i}" for i in range(1, 9)]),
        "t_names": _t_names,
        "t_units": _t_units,
        "p_names": _p_names,
        "p_units": _p_units,
    }

    return jsonify(data)


# --------------------------------------------------
# CONTROL ENDPOINTS
# --------------------------------------------------

@app.post("/api/control/pwm")
def api_control_pwm():
    data = request.get_json(force=True)

    pwm_cfg = _cfg.get("pwm", {})
    period_cfg = pwm_cfg.get("period", {})
    duty_cfg = pwm_cfg.get("duty", {})

    period = float(data.get("period", period_cfg.get("default", 1000)))
    duty = float(data.get("duty", duty_cfg.get("default", 50)))

    period = max(period_cfg.get("min", 0), min(period, period_cfg.get("max", 999999)))
    duty = max(duty_cfg.get("min", 0), min(duty, duty_cfg.get("max", 100)))

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control (parameter,value,source) VALUES (%s,%s,'hmi')",
                ("pwm_period", str(period))
            )
            cur.execute(
                "INSERT INTO control (parameter,value,source) VALUES (%s,%s,'hmi')",
                ("pwm_duty", str(duty))
            )
        return jsonify({"status": "OK"})
    except Exception:
        return jsonify({"status": "ERR"})


@app.post("/api/control/pid")
def api_control_pid():
    data = request.get_json(force=True)

    pid_cfg = _cfg.get("pid", {})

    def clamp(value, cfg):
        value = float(value)
        return max(cfg.get("min", 0), min(value, cfg.get("max", 1000)))

    t_set = clamp(data.get("t_set", pid_cfg["t_set"]["default"]), pid_cfg["t_set"])
    t_full = clamp(data.get("t_full", pid_cfg["t_full"]["default"]), pid_cfg["t_full"])
    t_move = clamp(data.get("t_move", pid_cfg["t_move"]["default"]), pid_cfg["t_move"])

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO control (parameter,value,source) VALUES (%s,%s,'hmi')", ("pid_t_set", str(t_set)))
            cur.execute("INSERT INTO control (parameter,value,source) VALUES (%s,%s,'hmi')", ("pid_t_full", str(t_full)))
            cur.execute("INSERT INTO control (parameter,value,source) VALUES (%s,%s,'hmi')", ("pid_t_move", str(t_move)))
        return jsonify({"status": "OK"})
    except Exception:
        return jsonify({"status": "ERR"})


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    host = _hmi_cfg.get("host", "0.0.0.0")
    port = int(_hmi_cfg.get("port", 8050))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    initialize_control_defaults()
    main()