"""Utilidades para ejecutar queries SQL externas y leer resultados como dicts."""
import os
import mysql.connector


QUERIES_DIR = os.path.join(os.path.dirname(__file__), "..", "queries")


def load_sql(filename: str) -> str:
    path = os.path.join(QUERIES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def ejecutar_query(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def ejecutar_reporte(conn, nombre_archivo: str, params: tuple = ()) -> list[dict]:
    sql = load_sql(nombre_archivo)
    return ejecutar_query(conn, sql, params)


def scalar(conn, sql: str, params: tuple = ()):
    rows = ejecutar_query(conn, sql, params)
    if not rows:
        return None
    return list(rows[0].values())[0]
