"""
Fixtures para tests de reportes sobre la BD desnormalizada (comercial_desn_db).
Conecta a DB_DESN_* y siembra directamente en tablas d_*.
Sobrescribe db_connection y rollback del conftest padre para esta carpeta.
"""
import os
import pytest
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

_DESN_CONFIG = {
    "host":     os.getenv("DB_DESN_HOST", "localhost"),
    "port":     int(os.getenv("DB_DESN_PORT", 3306)),
    "user":     os.getenv("DB_DESN_USER", "root"),
    "password": os.getenv("DB_DESN_PASSWORD", ""),
    "database": os.getenv("DB_DESN_NAME", "comercial_desn_db"),
}


@pytest.fixture(scope="session")
def db_connection():
    conn = mysql.connector.connect(**_DESN_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def rollback(db_connection):
    db_connection.start_transaction()
    yield
    db_connection.rollback()
