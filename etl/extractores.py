"""
Extracción de datos desde comercial_desn_db (tablas d_*).

Cada función retorna:
- Un iterador de chunks (tablas grandes, usa chunksize) o
- Un DataFrame completo (tablas pequeñas o consultas acotadas).

Nunca se usa fetchall() sobre el cursor directo.
El parámetro `watermark` limita la lectura a registros modificados desde la
última corrida exitosa, habilitando la carga incremental.
"""
import logging
from typing import Iterator

import pandas as pd
from sqlalchemy import text

from .conexiones import engine_desn

log = logging.getLogger(__name__)

CHUNKSIZE = 10_000

# ---------------------------------------------------------------------------
# Mapas de tipos optimizados — reducen footprint RAM 50-70 %
# ---------------------------------------------------------------------------
_TIPOS_INVENTARIO = {
    "id_producto":     "int32",
    "id_presentacion": "int32",
    "id_bodega":       "int32",
}

_TIPOS_MOVIMIENTOS = {
    "id_producto":     "int32",
    "id_bodega":       "int32",
    "tipo_movimiento": "category",
    "tipo_referencia": "category",
}

_TIPOS_FACTURAS = {
    "id_sucursal": "int32",
    "id_cliente":  "int32",
    "estado":      "category",
}

_TIPOS_DETALLE = {
    "id_factura":     "int32",
    "id_sucursal":    "int32",
    "id_producto":    "int32",
    "estado_factura": "category",
}

_TIPOS_ORDENES = {
    "id_proveedor": "int32",
    "estado":       "category",
}


def _cast(df: pd.DataFrame, tipos: dict) -> pd.DataFrame:
    """Aplica tipos solo a columnas presentes en el DataFrame."""
    return df.astype({k: v for k, v in tipos.items() if k in df.columns})


# ---------------------------------------------------------------------------
# d_inventario — tabla pequeña, carga completa
# ---------------------------------------------------------------------------
def leer_inventario() -> pd.DataFrame:
    q = "SELECT * FROM d_inventario WHERE deleted_at IS NULL"
    log.debug("Leyendo d_inventario completo")
    with engine_desn.connect() as conn:
        df = pd.read_sql(text(q), conn)
    return _cast(df, _TIPOS_INVENTARIO)


# ---------------------------------------------------------------------------
# d_movimientos_inventario — tabla grande, incremental por watermark en fecha
# ---------------------------------------------------------------------------
def leer_movimientos(watermark: str) -> Iterator[pd.DataFrame]:
    q = text(
        "SELECT id AS id_movimiento_orig, id_producto, codigo_producto, nombre_producto,"
        "       id_bodega, bodega, created_at AS fecha, tipo_movimiento,"
        "       cantidad, cantidad_anterior, cantidad_posterior,"
        "       costo_unitario, tipo_referencia, id_referencia, observacion,"
        "       deleted_at"
        "  FROM d_movimientos_inventario"
        " WHERE deleted_at IS NULL"
        "   AND updated_at > :wm"
        " ORDER BY fecha ASC"
    )
    log.debug("Leyendo d_movimientos_inventario desde watermark=%s", watermark)
    with engine_desn.connect() as conn:
        chunks = pd.read_sql(q, conn, params={"wm": watermark}, chunksize=CHUNKSIZE)
        for chunk in chunks:
            yield _cast(chunk, _TIPOS_MOVIMIENTOS)


def get_max_updated_movimientos() -> str:
    with engine_desn.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(updated_at) FROM d_movimientos_inventario WHERE deleted_at IS NULL")
        ).fetchone()
    return str(row[0]) if (row and row[0]) else "1900-01-01 00:00:00"


# ---------------------------------------------------------------------------
# d_facturas — UPSERT: estado y saldo pueden cambiar
# ---------------------------------------------------------------------------
def leer_facturas(watermark: str) -> Iterator[pd.DataFrame]:
    q = text(
        "SELECT id AS id_factura_orig, numero_factura,"
        "       fecha_emision, fecha_vencimiento,"
        "       id_sucursal, sucursal, id_cliente, cliente,"
        "       subtotal, descuento, impuesto, total, saldo, estado,"
        "       deleted_at"
        "  FROM d_facturas"
        " WHERE updated_at > :wm"
        " ORDER BY fecha_emision, id_factura_orig"
    )
    log.debug("Leyendo d_facturas desde watermark=%s", watermark)
    with engine_desn.connect() as conn:
        chunks = pd.read_sql(q, conn, params={"wm": watermark}, chunksize=CHUNKSIZE)
        for chunk in chunks:
            yield _cast(chunk, _TIPOS_FACTURAS)


def get_max_updated_facturas() -> str:
    with engine_desn.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(updated_at) FROM d_facturas")
        ).fetchone()
    return str(row[0]) if (row and row[0]) else "1900-01-01 00:00:00"


# ---------------------------------------------------------------------------
# d_facturas_detalle — tabla grande, incremental por watermark
# ---------------------------------------------------------------------------
def leer_facturas_detalle(watermark: str) -> Iterator[pd.DataFrame]:
    q = text(
        "SELECT id AS id_detalle_orig, id_factura, numero_factura,"
        "       fecha_emision, id_sucursal, estado_factura,"
        "       id_producto, codigo_producto, nombre_producto,"
        "       id_categoria, categoria,"
        "       cantidad, subtotal, costo_unitario,"
        "       deleted_at"
        "  FROM d_facturas_detalle"
        " WHERE updated_at > :wm"
        " ORDER BY fecha_emision, id_factura, id_detalle_orig"
    )
    log.debug("Leyendo d_facturas_detalle desde watermark=%s", watermark)
    with engine_desn.connect() as conn:
        chunks = pd.read_sql(q, conn, params={"wm": watermark}, chunksize=CHUNKSIZE)
        for chunk in chunks:
            yield _cast(chunk, _TIPOS_DETALLE)


def get_max_updated_detalle() -> str:
    with engine_desn.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(updated_at) FROM d_facturas_detalle")
        ).fetchone()
    return str(row[0]) if (row and row[0]) else "1900-01-01 00:00:00"


# ---------------------------------------------------------------------------
# d_ordenes_compra — UPSERT: estado puede cambiar
# ---------------------------------------------------------------------------
def leer_ordenes_compra(watermark: str) -> Iterator[pd.DataFrame]:
    q = text(
        "SELECT id AS id_orden_orig, id_proveedor, proveedor,"
        "       fecha_emision, estado, total,"
        "       deleted_at"
        "  FROM d_ordenes_compra"
        " WHERE updated_at > :wm"
        " ORDER BY fecha_emision, id_orden_orig"
    )
    log.debug("Leyendo d_ordenes_compra desde watermark=%s", watermark)
    with engine_desn.connect() as conn:
        chunks = pd.read_sql(q, conn, params={"wm": watermark}, chunksize=CHUNKSIZE)
        for chunk in chunks:
            yield _cast(chunk, _TIPOS_ORDENES)


def get_max_updated_ordenes() -> str:
    with engine_desn.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(updated_at) FROM d_ordenes_compra")
        ).fetchone()
    return str(row[0]) if (row and row[0]) else "1900-01-01 00:00:00"
