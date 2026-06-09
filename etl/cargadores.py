"""
Escritura de datos en comercial_resumen_db (tablas r_*).

Tres estrategias según el tipo de tabla:

1. truncar_y_cargar   — TRUNCATE + INSERT (full reload para snapshots)
2. cargar_incremental — INSERT solo registros nuevos (append-only)
3. upsert             — INSERT … ON DUPLICATE KEY UPDATE (registros mutables)

Todas usan to_sql con method="multi" (INSERT multi-row) y transacciones
por chunk para mantener el undo log pequeño.
"""
import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import Table, MetaData

from .conexiones import engine_resumen

log = logging.getLogger(__name__)

CHUNKSIZE_CARGA = 5_000


# ---------------------------------------------------------------------------
# Full reload
# ---------------------------------------------------------------------------

def truncar_y_cargar(df: pd.DataFrame, tabla: str, dry_run: bool = False) -> int:
    """TRUNCATE + INSERT. Idempotente. Para tablas tipo snapshot (r_inventario)."""
    if dry_run:
        log.info("[%s] DRY-RUN: %d filas listas (no se escribe)", tabla, len(df))
        return len(df)

    with engine_resumen.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text(f"TRUNCATE TABLE {tabla}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    if df.empty:
        log.info("[%s] DataFrame vacío, destino truncado", tabla)
        return 0

    df.to_sql(
        tabla, engine_resumen,
        if_exists="append", index=False,
        chunksize=CHUNKSIZE_CARGA, method="multi",
    )
    log.info("[%s] full reload: %d filas", tabla, len(df))
    return len(df)


# ---------------------------------------------------------------------------
# Carga incremental (append-only)
# ---------------------------------------------------------------------------

def cargar_incremental(df: pd.DataFrame, tabla: str, dry_run: bool = False) -> int:
    """
    INSERT de registros nuevos por lotes. Cada lote tiene su propia transacción.
    Para tablas cuyos registros no cambian una vez creados
    (r_movimientos_inventario, r_facturas_detalle).
    """
    if df.empty:
        return 0
    if dry_run:
        log.info("[%s] DRY-RUN: %d filas listas (no se escribe)", tabla, len(df))
        return len(df)

    total = 0
    for inicio in range(0, len(df), CHUNKSIZE_CARGA):
        chunk = df.iloc[inicio: inicio + CHUNKSIZE_CARGA]
        with engine_resumen.begin() as conn:
            chunk.to_sql(
                tabla, conn,
                if_exists="append", index=False, method="multi",
            )
        total += len(chunk)
        log.debug("[%s] %d/%d filas insertadas", tabla, total, len(df))

    log.info("[%s] incremental: %d filas insertadas", tabla, total)
    return total


# ---------------------------------------------------------------------------
# UPSERT (INSERT … ON DUPLICATE KEY UPDATE)
# ---------------------------------------------------------------------------

def upsert(df: pd.DataFrame, tabla: str, cols_update: list, dry_run: bool = False) -> int:
    """
    INSERT con ON DUPLICATE KEY UPDATE para `cols_update`.
    Requiere UNIQUE KEY en la tabla destino.
    Para tablas cuyos registros pueden mutar (r_facturas, r_ordenes_compra).
    """
    if df.empty:
        return 0
    if dry_run:
        log.info("[%s] DRY-RUN: %d filas listas (no se escribe)", tabla, len(df))
        return len(df)

    meta = MetaData()
    meta.reflect(bind=engine_resumen, only=[tabla])
    tbl = meta.tables[tabla]

    total = 0
    for inicio in range(0, len(df), CHUNKSIZE_CARGA):
        chunk = df.iloc[inicio: inicio + CHUNKSIZE_CARGA]
        registros = chunk.where(pd.notna(chunk), None).to_dict("records")
        registros = [
            {k: v.to_pydatetime() if isinstance(v, pd.Timestamp) else v
             for k, v in r.items()}
            for r in registros
        ]

        stmt = mysql_insert(tbl).values(registros)
        update_dict = {c: stmt.inserted[c] for c in cols_update if c in tbl.c}
        stmt = stmt.on_duplicate_key_update(**update_dict)

        with engine_resumen.begin() as conn:
            conn.execute(stmt)
        total += len(chunk)
        log.debug("[%s] %d/%d filas upserted", tabla, total, len(df))

    log.info("[%s] upsert: %d filas", tabla, total)
    return total


# ---------------------------------------------------------------------------
# Reconciliación post-carga
# ---------------------------------------------------------------------------

def validar_conteo(cnt_src: int, tabla_dst: str, filtro: str = "") -> bool:
    """
    Compara `cnt_src` (registros procesados) con el COUNT real en destino.
    Registra una advertencia si difieren; no lanza excepción para no bloquear el pipeline.
    """
    with engine_resumen.connect() as conn:
        cnt_dst = conn.execute(
            text(f"SELECT COUNT(*) FROM {tabla_dst} {filtro}")
        ).scalar()

    if cnt_src != cnt_dst:
        log.warning(
            "[%s] reconciliación: procesados=%d, destino=%d",
            tabla_dst, cnt_src, cnt_dst,
        )
        return False

    log.debug("[%s] reconciliación OK: %d filas", tabla_dst, cnt_dst)
    return True
