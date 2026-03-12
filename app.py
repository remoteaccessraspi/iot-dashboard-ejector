from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
import yaml
import pymysql

# --------------------------------------------------
# INIT
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

# --------------------------------------------------
# LOAD CONFIG
# --------------------------------------------------

def load_cfg():
    return yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8"))

_cfg = load_cfg()
_db_cfg = _cfg["database"]
_refresh_ms = _cfg.get("hmi", {}).get("refresh_ms", 2000)

# --------------------------------------------------
# DB
# --------------------------------------------------

def db_connect():
    return pymysql.connect(
        host=_db_cfg["host"],
        port=int(_db_cfg.get("port", 3306)),
        user=_db_cfg["user"],
        password=_db_cfg["password"],
        database=_db_cfg["name"],
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )

def latest_row(table):
    try:
        conn = db_connect()
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}` ORDER BY id DESC LIMIT 1")
            return cur.fetchone()
    except:
        return None

def latest_ts(table):
    try:
        conn = db_connect()
        with conn.cursor() as cur:
            cur.execute(f"SELECT ts FROM `{table}` ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row.get("ts"):
                return row["ts"]
    except:
        return None
    finally:
        conn.close()

# --------------------------------------------------
# CHANNEL UTIL
# --------------------------------------------------

def build_channel_cfg(prefix):

    channels = _cfg.get("channels", {})

    names = []
    units = []

    for i in range(1,9):
        ch = channels.get(f"{prefix}{i}", {})
        names.append(ch.get("name", f"{prefix}{i}"))
        units.append(ch.get("unit", ""))

    return names, units


def pick(row, prefix):

    if not row:
        return [None]*8

    return [row.get(f"{prefix}{i}") for i in range(1,9)]

# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def monitor(request: Request):

    return templates.TemplateResponse(
        "monitor.html",
        {
            "request": request,
            "refresh_ms": _refresh_ms
        }
    )


@app.get("/control", response_class=HTMLResponse)
def control_page(request: Request):

    return templates.TemplateResponse(
        "control.html",
        {
            "request": request,
            "pwm": _cfg.get("pwm", {}),
            "pid": _cfg.get("pid", {})
        }
    )

# --------------------------------------------------
# API MONITOR
# --------------------------------------------------

@app.get("/api/latest")
def api_latest():

    db_ok = True

    try:

        trow = latest_row("temperature") or {}
        irow = latest_row("current_loop") or {}
        prow = latest_row("conversion_table") or {}

        t_last = latest_ts("temperature")
        i_last = latest_ts("current_loop")

    except:

        db_ok = False
        trow = {}
        irow = {}
        prow = {}
        t_last = None
        i_last = None

    # --------------------------------------------------
    # CHANNEL CONFIG
    # --------------------------------------------------

    t_names, t_units = build_channel_cfg("t")
    i_names, i_units = build_channel_cfg("i")
    p_names, p_units = build_channel_cfg("p")

    # --------------------------------------------------
    # RELAYS
    # --------------------------------------------------

    relay_cfg = _cfg.get("relay", {})
    relay_control_cfg = relay_cfg.get("control", {})
    relay_names_cfg = relay_cfg.get("names", {})
    relay_count = relay_cfg.get("count", 8)

    relay_states = {f"r{i}":0 for i in range(1, relay_count+1)}

    try:

        conn = db_connect()

        with conn.cursor() as cur:

            cur.execute("SELECT name,state FROM relay_state")

            rows = cur.fetchall()

            for r in rows:
                relay_states[r["name"]] = r["state"]

        conn.close()

    except:

        db_ok = False

    r_values=[]
    r_names=[]
    r_modes=[]

    for i in range(1,relay_count+1):

        name=f"r{i}"

        r_values.append(relay_states.get(name,0))
        r_names.append(relay_names_cfg.get(name,name))
        r_modes.append(relay_control_cfg.get(name,{}).get("mode","manual"))

    # --------------------------------------------------
    # RETURN
    # --------------------------------------------------

    return {

        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "refresh_ms": _refresh_ms,
        "db_status": "OK" if db_ok else "ERR",

        "t": pick(trow,"t"),
        "i": pick(irow,"i"),
        "p": pick(prow,"p"),

        "t_names": t_names,
        "t_units": t_units,

        "i_names": i_names,
        "i_units": i_units,

        "p_names": p_names,
        "p_units": p_units,

        "t_last_db": t_last.strftime("%Y-%m-%d %H:%M:%S") if t_last else None,
        "i_last_db": i_last.strftime("%Y-%m-%d %H:%M:%S") if i_last else None,

        "r": r_values,
        "r_names": r_names,
        "r_modes": r_modes,
    }

# --------------------------------------------------
# RELAY PAGE
# --------------------------------------------------

@app.get("/relay", response_class=HTMLResponse)
def relay_page(request: Request):

    return templates.TemplateResponse(
        "relay.html",
        {
            "request": request,
            "refresh_ms": _refresh_ms
        }
    )

# --------------------------------------------------
# RELAY CONTROL
# --------------------------------------------------

@app.post("/api/relay/set")
async def api_relay_set(data: dict):

    name=data.get("name")
    state=int(data.get("state",0))

    relay_cfg=_cfg.get("relay",{})
    relay_control_cfg=relay_cfg.get("control",{})

    if relay_control_cfg.get(name,{}).get("mode")=="auto":
        return {"status":"DENIED","reason":"AUTO relay"}

    try:

        conn=db_connect()

        with conn.cursor() as cur:

            cur.execute("""
            INSERT INTO relay_state (name,state,source)
            VALUES (%s,%s,'hmi')
            ON DUPLICATE KEY UPDATE
            state=VALUES(state),
            source='hmi'
            """,(name,state))

        conn.close()

    except Exception as e:

        return {"status":"ERROR","detail":str(e)}

    return {"status":"OK"}

# --------------------------------------------------
# CONTROL
# --------------------------------------------------

@app.get("/api/control/latest")
def api_control_latest():

    result={
        "pwm_period":None,
        "pwm_duty":None,
        "pid_t_set":None,
        "pid_t_full":None,
        "pid_t_move":None,
    }

    try:

        conn=db_connect()

        with conn.cursor() as cur:

            for param in result.keys():

                cur.execute(
                    "SELECT value FROM control WHERE parameter=%s ORDER BY id DESC LIMIT 1",
                    (param,)
                )

                row=cur.fetchone()

                if row:
                    result[param]=float(row["value"])

        conn.close()

    except:
        pass

    return result