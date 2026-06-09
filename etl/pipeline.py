"""
Orquestador del ETL comercial_desn_db → comercial_resumen_db.

Estrategias por tabla:
  r_inventario              full reload      (snapshot de stock)
  r_movimientos_inventario  incremental      (append-only, watermark en fecha)
  r_facturas                upsert           (estado/saldo pueden cambiar)
  r_facturas_detalle        incremental      (líneas inmutables, watermark)
  r_ordenes_compra          upsert           (estado puede cambiar)

Las cinco tablas son independientes entre sí y se procesan en paralelo
(ThreadPoolExecutor — I/O-bound, GIL no es obstáculo).
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import control, extractores as ext, transformadores as tr, cargadores as carg

log = logging.getLogger("etl.pipeline")

# Columnas mutables para UPSERT (excluye created_at)
_UPSERT_FACTURAS = [
    "numero_factura", "fecha_emision", "fecha_vencimiento",
    "id_sucursal", "sucursal", "id_cliente", "cliente",
    "subtotal", "descuento", "impuesto", "total", "saldo",
    "estado", "deleted_at",
]
_UPSERT_ORDENES = [
    "id_proveedor", "proveedor", "fecha_emision",
    "estado", "total", "deleted_at",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Timer:
    def __enter__(self):
        self._t = time.perf_counter()
        return self
    def __exit__(self, *_):
        self.elapsed = time.perf_counter() - self._t


def _velocidad(filas: int, seg: float) -> str:
    return f"{filas / seg:,.0f} filas/s" if seg > 0 else "—"


# ---------------------------------------------------------------------------
# Procesadores individuales
# ---------------------------------------------------------------------------

def _proc_inventario(dry_run: bool) -> int:
    tabla = "r_inventario"
    run_id = control.registrar_inicio(tabla)
    try:
        with _Timer() as t:
            df_raw = ext.leer_inventario()
            df     = tr.transformar_inventario(df_raw)
            filas  = carg.truncar_y_cargar(df, tabla, dry_run)
        log.info("[%s] %d filas en %.1fs (%s)", tabla, filas, t.elapsed, _velocidad(filas, t.elapsed))
        control.registrar_fin(run_id, tabla, filas, watermark=None)
    except Exception as exc:
        control.registrar_fin(run_id, tabla, 0, error=str(exc))
        raise
    return filas


def _proc_movimientos(dry_run: bool) -> int:
    tabla = "r_movimientos_inventario"
    watermark = control.get_watermark(tabla)
    run_id = control.registrar_inicio(tabla)
    total = 0
    try:
        with _Timer() as t:
            for chunk in ext.leer_movimientos(watermark):
                df = tr.transformar_movimientos(chunk)
                total += carg.cargar_incremental(df, tabla, dry_run)
        new_wm = ext.get_max_updated_movimientos()
        log.info("[%s] %d filas en %.1fs (%s)", tabla, total, t.elapsed, _velocidad(total, t.elapsed))
        control.registrar_fin(run_id, tabla, total, watermark=new_wm)
    except Exception as exc:
        control.registrar_fin(run_id, tabla, total, error=str(exc))
        raise
    return total


def _proc_facturas(dry_run: bool) -> int:
    tabla = "r_facturas"
    watermark = control.get_watermark(tabla)
    run_id = control.registrar_inicio(tabla)
    total = 0
    try:
        with _Timer() as t:
            for chunk in ext.leer_facturas(watermark):
                df = tr.transformar_facturas(chunk)
                total += carg.upsert(df, tabla, _UPSERT_FACTURAS, dry_run)
        new_wm = ext.get_max_updated_facturas()
        log.info("[%s] %d filas en %.1fs (%s)", tabla, total, t.elapsed, _velocidad(total, t.elapsed))
        control.registrar_fin(run_id, tabla, total, watermark=new_wm)
    except Exception as exc:
        control.registrar_fin(run_id, tabla, total, error=str(exc))
        raise
    return total


def _proc_facturas_detalle(dry_run: bool) -> int:
    tabla = "r_facturas_detalle"
    watermark = control.get_watermark(tabla)
    run_id = control.registrar_inicio(tabla)
    total = 0
    try:
        with _Timer() as t:
            for chunk in ext.leer_facturas_detalle(watermark):
                df = tr.transformar_facturas_detalle(chunk)
                total += carg.cargar_incremental(df, tabla, dry_run)
        new_wm = ext.get_max_updated_detalle()
        log.info("[%s] %d filas en %.1fs (%s)", tabla, total, t.elapsed, _velocidad(total, t.elapsed))
        control.registrar_fin(run_id, tabla, total, watermark=new_wm)
    except Exception as exc:
        control.registrar_fin(run_id, tabla, total, error=str(exc))
        raise
    return total


def _proc_ordenes_compra(dry_run: bool) -> int:
    tabla = "r_ordenes_compra"
    watermark = control.get_watermark(tabla)
    run_id = control.registrar_inicio(tabla)
    total = 0
    try:
        with _Timer() as t:
            for chunk in ext.leer_ordenes_compra(watermark):
                df = tr.transformar_ordenes_compra(chunk)
                total += carg.upsert(df, tabla, _UPSERT_ORDENES, dry_run)
        new_wm = ext.get_max_updated_ordenes()
        log.info("[%s] %d filas en %.1fs (%s)", tabla, total, t.elapsed, _velocidad(total, t.elapsed))
        control.registrar_fin(run_id, tabla, total, watermark=new_wm)
    except Exception as exc:
        control.registrar_fin(run_id, tabla, total, error=str(exc))
        raise
    return total


# ---------------------------------------------------------------------------
# Catálogo de tablas disponibles
# ---------------------------------------------------------------------------

TABLAS: dict[str, callable] = {
    "r_inventario":             _proc_inventario,
    "r_movimientos_inventario": _proc_movimientos,
    "r_facturas":               _proc_facturas,
    "r_facturas_detalle":       _proc_facturas_detalle,
    "r_ordenes_compra":         _proc_ordenes_compra,
}


# ---------------------------------------------------------------------------
# Ejecución paralela
# ---------------------------------------------------------------------------

def ejecutar(
    tablas: list[str] = None,
    dry_run: bool = False,
    max_workers: int = 4,
) -> bool:
    """
    Ejecuta el ETL para las tablas indicadas (o todas si `tablas` es None).
    Retorna True si todas completaron sin error.
    """
    tablas_a_procesar = tablas if tablas else list(TABLAS.keys())
    invalidas = [t for t in tablas_a_procesar if t not in TABLAS]
    if invalidas:
        raise ValueError(f"Tablas desconocidas: {invalidas}. Opciones: {list(TABLAS)}")

    prefijo = "(DRY-RUN) " if dry_run else ""
    log.info("=== ETL Resumen %s— %d tabla(s) ===", prefijo, len(tablas_a_procesar))

    resultados: dict[str, tuple] = {}

    with _Timer() as t_total:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(tablas_a_procesar))) as pool:
            futures = {
                pool.submit(TABLAS[t], dry_run): t
                for t in tablas_a_procesar
            }
            for fut in as_completed(futures):
                tabla = futures[fut]
                try:
                    filas = fut.result()
                    resultados[tabla] = ("ok", filas)
                except Exception as exc:
                    resultados[tabla] = ("error", str(exc))
                    log.error("[%s] FALLIDA: %s", tabla, exc)

    log.info("=== Completado en %.1fs ===", t_total.elapsed)
    for tabla in tablas_a_procesar:
        estado, detalle = resultados.get(tabla, ("?", "sin resultado"))
        marca = "OK" if estado == "ok" else "ERROR"
        log.info("  [%s] %s — %s", marca, tabla, detalle)

    return all(e == "ok" for e, _ in resultados.values())
