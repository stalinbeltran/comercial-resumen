"""Crea las BDs de test importando los esquemas de producción sin los DDL de DB."""
import re
import subprocess
import sys

MYSQL = r"C:\Program Files\MariaDB 12.3\bin\mysql.exe"
MYSQL_ARGS = ["-u", "root", "-pstalin"]


def strip_db_ddl(sql: str) -> str:
    """Elimina CREATE DATABASE ... y USE ... del SQL."""
    # Elimina bloques CREATE DATABASE ... ; (puede abarcar varias líneas)
    sql = re.sub(
        r"CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS\s+\S+[^;]*;",
        "",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Elimina USE db_name;
    sql = re.sub(r"USE\s+\S+\s*;", "", sql, flags=re.IGNORECASE)
    return sql


def run_sql(db: str, sql: str):
    result = subprocess.run(
        [MYSQL] + MYSQL_ARGS + [db],
        input=sql.encode("utf-8"),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR al importar en {db}:")
        print(result.stderr.decode("utf-8", errors="replace"))
        sys.exit(1)
    print(f"OK: esquema importado en {db}")


pairs = [
    ("db/create/create_desnormalizada.sql", "comercial_desn_test"),
    ("db/create/create_resumen.sql",        "comercial_resumen_test"),
]

for sql_file, db_name in pairs:
    with open(sql_file, encoding="utf-8") as f:
        sql = f.read()
    run_sql(db_name, strip_db_ddl(sql))

print("Listo. BDs de test creadas.")
