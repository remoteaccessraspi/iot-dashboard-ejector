import mysql.connector

DB_USER = "dbapp"
DB_PASS = "admin"
DB_NAME = "ejector"
DB_SOCKET = "/run/mysqld/mysqld.sock"


def main() -> None:
    conn = mysql.connector.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        unix_socket=DB_SOCKET,
        autocommit=True,
        connection_timeout=5,
    )

    cur = conn.cursor()

    cur.execute("SELECT 1")
    print("SELECT 1 ->", cur.fetchone())

    cur.execute("SELECT machine_type, hw_version, sw_version FROM system_info LIMIT 1")
    print("system_info ->", cur.fetchone())

    cur.execute(
        "INSERT INTO system (component, level, message) VALUES (%s,%s,%s)",
        ("db_test", "INFO", "DB socket test OK"),
    )
    last_id = cur.lastrowid
    print("Inserted system id ->", last_id)

    cur.execute("SELECT id, ts, component, level, message FROM system WHERE id=%s", (last_id,))
    print("Readback ->", cur.fetchone())

    cur.close()
    conn.close()
    print("DONE ✅")


if __name__ == "__main__":
    main()