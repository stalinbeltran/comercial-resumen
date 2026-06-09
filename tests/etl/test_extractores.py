"""
Tests de integración de etl/extractores.py.
Verifican que las queries SQL lean correctamente desde la BD fuente de test.
"""
import pytest
from sqlalchemy import text

import etl.extractores as ext
from tests.etl.helpers import (
    insertar_d_inventario, insertar_d_movimientos,
    insertar_d_facturas, insertar_d_detalle, insertar_d_ordenes,
    forzar_updated_at,
    INVENTARIO_BASE, MOVIMIENTO_BASE, FACTURA_BASE, DETALLE_BASE, ORDEN_BASE,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# leer_inventario
# ---------------------------------------------------------------------------

class TestLeerInventario:

    def test_retorna_todas_las_filas_activas(self, engine_src, patch_engines):
        insertar_d_inventario(engine_src, [INVENTARIO_BASE, {**INVENTARIO_BASE, "id_producto": 2}])
        df = ext.leer_inventario()
        assert len(df) == 2

    def test_excluye_filas_con_deleted_at(self, engine_src, patch_engines):
        insertar_d_inventario(engine_src, [INVENTARIO_BASE])
        with engine_src.begin() as conn:
            conn.execute(text("UPDATE d_inventario SET deleted_at = NOW()"))
        df = ext.leer_inventario()
        assert len(df) == 0

    def test_columna_id_producto_es_int(self, engine_src, patch_engines):
        insertar_d_inventario(engine_src, [INVENTARIO_BASE])
        df = ext.leer_inventario()
        assert df["id_producto"].dtype in ("int32", "int64")


# ---------------------------------------------------------------------------
# leer_facturas
# ---------------------------------------------------------------------------

class TestLeerFacturas:

    def test_retorna_filas_con_updated_at_mayor_que_watermark(self, engine_src, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas", 1, "2026-06-01 10:00:00")

        chunks = list(ext.leer_facturas("2026-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 1

    def test_no_retorna_filas_con_updated_at_igual_al_watermark(self, engine_src, patch_engines):
        """Watermark usa >, no >=. Un registro con updated_at == watermark no debe reprocesarse."""
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas", 1, "2026-06-01 10:00:00")

        chunks = list(ext.leer_facturas("2026-06-01 10:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 0

    def test_no_retorna_filas_con_updated_at_menor_al_watermark(self, engine_src, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas", 1, "2025-12-31 00:00:00")

        chunks = list(ext.leer_facturas("2026-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 0

    def test_incluye_filas_con_deleted_at_para_propagar_borrado(self, engine_src, patch_engines):
        """Las facturas anuladas/borradas deben propagarse al destino vía UPSERT."""
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_facturas SET deleted_at = NOW(), updated_at = NOW() WHERE id = 1"
            ))

        chunks = list(ext.leer_facturas("1900-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 1

    def test_columna_id_factura_orig_presente(self, engine_src, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 5}])
        chunks = list(ext.leer_facturas("1900-01-01 00:00:00"))
        df = chunks[0]
        assert "id_factura_orig" in df.columns
        assert int(df["id_factura_orig"].iloc[0]) == 5


# ---------------------------------------------------------------------------
# leer_movimientos
# ---------------------------------------------------------------------------

class TestLeerMovimientos:

    def test_retorna_nuevos_registros_post_watermark(self, engine_src, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])

        chunks = list(ext.leer_movimientos("1900-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 1

    def test_no_retorna_registros_previos_al_watermark(self, engine_src, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_movimientos_inventario SET updated_at = '2025-01-01 00:00:00'"
            ))

        chunks = list(ext.leer_movimientos("2026-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 0

    def test_excluye_filas_con_deleted_at_en_fuente(self, engine_src, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_movimientos_inventario "
                "SET deleted_at = NOW(), updated_at = NOW()"
            ))

        chunks = list(ext.leer_movimientos("1900-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 0


# ---------------------------------------------------------------------------
# leer_ordenes_compra
# ---------------------------------------------------------------------------

class TestLeerOrdenesCompra:

    def test_retorna_ordenes_post_watermark(self, engine_src, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1}])

        chunks = list(ext.leer_ordenes_compra("1900-01-01 00:00:00"))
        total = sum(len(c) for c in chunks)
        assert total == 1

    def test_columna_id_orden_orig_presente(self, engine_src, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 7}])
        chunks = list(ext.leer_ordenes_compra("1900-01-01 00:00:00"))
        df = chunks[0]
        assert "id_orden_orig" in df.columns
        assert int(df["id_orden_orig"].iloc[0]) == 7


# ---------------------------------------------------------------------------
# get_max_updated_*
# ---------------------------------------------------------------------------

class TestGetMaxUpdated:

    def test_retorna_1900_cuando_tabla_vacia(self, engine_src, patch_engines):
        wm = ext.get_max_updated_facturas()
        assert wm == "1900-01-01 00:00:00"

    def test_retorna_max_updated_at_real(self, engine_src, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas", 1, "2026-03-15 12:00:00")
        wm = ext.get_max_updated_facturas()
        assert "2026-03-15" in wm
