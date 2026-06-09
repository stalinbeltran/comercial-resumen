"""
Fixtures de pytest para los tests del ETL comercial_desn_db → comercial_resumen_db.

Los engines apuntan a BDs de prueba (comercial_desn_test / comercial_resumen_test),
NUNCA a las productivas. Se construyen aquí — NO se importan de etl.conexiones.

Limpieza: TRUNCATE antes de cada test (no rollback, porque el pipeline hace
commits propios por chunk que no se pueden revertir).
"""
import os
from urllib.parse import quote_plus

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()


# ---------------------------------------------------------------------------
# Construcción de engines de test
# ---------------------------------------------------------------------------

def _build_test_engine(db_name_env: str):
    pw   = quote_plus(os.getenv("DB_DESN_PASSWORD", os.getenv("DB_PASSWORD", "")))
    user = os.getenv("DB_DESN_USER", os.getenv("DB_USER", "root"))
    host = os.getenv("DB_DESN_HOST", os.getenv("DB_HOST", "localhost"))
    port = os.getenv("DB_DESN_PORT", os.getenv("DB_PORT", "3306"))
    db   = os.getenv(db_name_env)
    if not db:
        raise EnvironmentError(f"{db_name_env} no está definido en .env")
    url = f"mysql+mysqlconnector://{user}:{pw}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="session")
def engine_src():
    """Engine hacia comercial_desn_test (fuente del ETL)."""
    return _build_test_engine("DB_DESN_TEST_NAME")


@pytest.fixture(scope="session")
def engine_dst():
    """Engine hacia comercial_resumen_test (destino del ETL)."""
    return _build_test_engine("DB_RESUMEN_TEST_NAME")


# ---------------------------------------------------------------------------
# Crear esquema de test si no existe (solo en la primera sesión)
# ---------------------------------------------------------------------------

_TABLAS_SRC = [
    "d_inventario",
    "d_movimientos_inventario",
    "d_facturas",
    "d_facturas_detalle",
    "d_ordenes_compra",
]

_TABLAS_DST = [
    "etl_runs",
    "r_inventario",
    "r_movimientos_inventario",
    "r_facturas",
    "r_facturas_detalle",
    "r_ordenes_compra",
]


@pytest.fixture(scope="session", autouse=True)
def crear_esquema_test(engine_src, engine_dst):
    """
    Verifica que las tablas de test existan.
    Si faltan, falla con instrucciones claras en lugar de un error críptico.
    """
    insp_src = inspect(engine_src)
    insp_dst = inspect(engine_dst)

    faltantes_src = [t for t in _TABLAS_SRC if not insp_src.has_table(t)]
    faltantes_dst = [t for t in _TABLAS_DST if not insp_dst.has_table(t)]

    if faltantes_src or faltantes_dst:
        msg = (
            "\nFaltan tablas en las BDs de test. Ejecuta:\n"
            "  mysql -u root -p comercial_desn_test   < db/create/create_desnormalizada.sql\n"
            "  mysql -u root -p comercial_resumen_test < db/create/create_resumen.sql\n"
        )
        if faltantes_src:
            msg += f"\nFaltantes en comercial_desn_test: {faltantes_src}"
        if faltantes_dst:
            msg += f"\nFaltantes en comercial_resumen_test: {faltantes_dst}"
        pytest.fail(msg)

    yield


# ---------------------------------------------------------------------------
# TRUNCATE antes de cada test — la única estrategia válida para ETL
# El pipeline hace commits propios que rollback no puede revertir.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def limpiar_fuente(engine_src):
    with engine_src.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in _TABLAS_SRC:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield


@pytest.fixture(autouse=True)
def limpiar_destino(engine_dst):
    with engine_dst.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in _TABLAS_DST:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield


# ---------------------------------------------------------------------------
# Parcheo de engines en módulos ETL
# Los módulos etl.* importan sus engines al nivel de módulo desde etl.conexiones.
# Para que usen las BDs de test hay que parchear cada referencia individual.
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_engines(engine_src, engine_dst, monkeypatch):
    """
    Redirige todos los engines del ETL hacia las BDs de test.
    Usar en tests de integración y pipeline que invocan funciones ETL directamente.
    """
    monkeypatch.setattr("etl.control.engine_resumen",     engine_dst)
    monkeypatch.setattr("etl.extractores.engine_desn",    engine_src)
    monkeypatch.setattr("etl.cargadores.engine_resumen",  engine_dst)
    return engine_src, engine_dst
