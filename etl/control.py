"""
Gestión de la tabla etl_runs en comercial_resumen_db.

Provee:
- registrar_inicio / registrar_fin  → auditoría de cada corrida
- get_watermark                     → último updated_at procesado exitosamente
"""
import logging
from sqlalchemy import text
from .conexiones import engine_resumen

log = logging.getLogger(__name__)


def get_watermark(tabla: str) -> str:
    """
    Retorna el watermark de la última corrida exitosa de `tabla`.
    Si no hay corrida previa, retorna '1900-01-01 00:00:00' para procesar todo.
    """
    with engine_resumen.connect() as conn:
        row = conn.execute(
            text(
                "SELECT MAX(watermark) FROM etl_runs "
                "WHERE tabla = :t AND estado = 'ok'"
            ),
            {"t": tabla},
        ).fetchone()
    wm = str(row[0]) if (row and row[0]) else "1900-01-01 00:00:00"
    log.debug("[%s] watermark = %s", tabla, wm)
    return wm


def registrar_inicio(tabla: str) -> int:
    """Inserta un run en estado 'running' y retorna su id."""
    with engine_resumen.begin() as conn:
        result = conn.execute(
            text("INSERT INTO etl_runs (tabla, estado) VALUES (:t, 'running')"),
            {"t": tabla},
        )
        run_id = result.lastrowid
    log.info("[%s] run #%d iniciado", tabla, run_id)
    return run_id


def registrar_fin(
    run_id: int,
    tabla: str,
    filas: int,
    watermark: str = None,
    error: str = None,
) -> None:
    """Cierra el run con estado 'ok' o 'error'."""
    estado = "error" if error else "ok"
    with engine_resumen.begin() as conn:
        conn.execute(
            text(
                "UPDATE etl_runs "
                "SET fin = NOW(), filas = :f, estado = :e, "
                "    watermark = :w, mensaje = :m "
                "WHERE id = :id"
            ),
            {"f": filas, "e": estado, "w": watermark, "m": error, "id": run_id},
        )
    if error:
        log.error("[%s] run #%d FALLIDO: %s", tabla, run_id, error)
    else:
        log.info(
            "[%s] run #%d completado — %d filas, watermark = %s",
            tabla, run_id, filas, watermark,
        )
