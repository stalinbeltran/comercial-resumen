"""
Engines SQLAlchemy para comercial_desn_db (origen) y comercial_resumen_db (destino).

Usar siempre estos engines en lugar de conexiones DBAPI directas:
- pool_pre_ping reconecta si MySQL cerró la conexión por timeout.
- pool_recycle evita conexiones "muertas" en ETLs largos.
"""
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, Engine
from dotenv import load_dotenv

load_dotenv()


def _build_engine(prefix: str = "") -> Engine:
    sep = f"_{prefix}" if prefix else ""
    user     = os.getenv(f"DB{sep}_USER", "root")
    password = quote_plus(os.getenv(f"DB{sep}_PASSWORD", ""))
    host     = os.getenv(f"DB{sep}_HOST", "localhost")
    port     = os.getenv(f"DB{sep}_PORT", "3306")
    database = os.getenv(f"DB{sep}_NAME")

    if not database:
        raise EnvironmentError(f"DB{sep}_NAME no está definido en .env")

    url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=6,
        max_overflow=4,
    )


engine_desn    = _build_engine("DESN")
engine_resumen = _build_engine("RESUMEN")
