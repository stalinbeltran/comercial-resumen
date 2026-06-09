"""
Tests end-to-end del procesador r_ordenes_compra.
Estrategia: UPSERT — el estado de una orden puede cambiar (borrador → recibida).
"""
import pytest
from sqlalchemy import text

from etl.pipeline import _proc_ordenes_compra
from tests.etl.helpers import (
    insertar_d_ordenes, forzar_updated_at, contar, leer_campo, ultimo_run,
    ORDEN_BASE,
)

pytestmark = pytest.mark.pipeline


class TestOrdenesCompraUpsert:

    def test_primera_corrida_carga_todas_las_ordenes(self, engine_src, engine_dst, patch_engines):
        """
        DADO   3 órdenes de compra en d_ordenes_compra
        CUANDO se ejecuta _proc_ordenes_compra por primera vez
        ENTONCES r_ordenes_compra tiene exactamente 3 filas
        """
        insertar_d_ordenes(engine_src, [
            {**ORDEN_BASE, "id": 1},
            {**ORDEN_BASE, "id": 2, "fecha_emision": "2026-02-01"},
            {**ORDEN_BASE, "id": 3, "fecha_emision": "2026-03-01"},
        ])

        filas = _proc_ordenes_compra(dry_run=False)

        assert filas == 3
        assert contar(engine_dst, "r_ordenes_compra") == 3

    def test_segunda_corrida_sin_cambios_no_duplica(self, engine_src, engine_dst, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1}])
        _proc_ordenes_compra(dry_run=False)
        filas_segunda = _proc_ordenes_compra(dry_run=False)

        assert filas_segunda == 0
        assert contar(engine_dst, "r_ordenes_compra") == 1

    def test_upsert_actualiza_estado_borrador_a_recibida(self, engine_src, engine_dst, patch_engines):
        """
        DADO   orden en estado 'borrador' ya cargada
        CUANDO cambia a 'recibida' en la fuente
        ENTONCES r_ordenes_compra refleja el nuevo estado
        """
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1, "estado": "borrador"}])
        _proc_ordenes_compra(dry_run=False)

        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_ordenes_compra SET estado = 'recibida', updated_at = NOW() WHERE id = 1"
            ))
        _proc_ordenes_compra(dry_run=False)

        estado = leer_campo(engine_dst, "r_ordenes_compra", "estado",
                            "id_orden_orig = :id", {"id": 1})
        assert estado == "recibida"

    def test_upsert_actualiza_total_si_cambia(self, engine_src, engine_dst, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1, "total": 1000.00}])
        _proc_ordenes_compra(dry_run=False)

        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_ordenes_compra SET total = 1500.00, updated_at = NOW() WHERE id = 1"
            ))
        _proc_ordenes_compra(dry_run=False)

        total = leer_campo(engine_dst, "r_ordenes_compra", "total",
                           "id_orden_orig = :id", {"id": 1})
        assert float(total) == 1500.00

    def test_solo_ordenes_post_watermark_se_reprocesen(self, engine_src, engine_dst, patch_engines):
        insertar_d_ordenes(engine_src, [
            {**ORDEN_BASE, "id": 1},
            {**ORDEN_BASE, "id": 2, "fecha_emision": "2026-02-01"},
        ])
        forzar_updated_at(engine_src, "d_ordenes_compra", 1, "2026-01-01 00:00:00")
        forzar_updated_at(engine_src, "d_ordenes_compra", 2, "2026-01-01 00:00:00")
        _proc_ordenes_compra(dry_run=False)

        filas_segunda = _proc_ordenes_compra(dry_run=False)
        assert filas_segunda == 0

    def test_dry_run_no_escribe(self, engine_src, engine_dst, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1}])
        _proc_ordenes_compra(dry_run=True)
        assert contar(engine_dst, "r_ordenes_compra") == 0

    def test_etl_runs_ok_con_watermark(self, engine_src, engine_dst, patch_engines):
        insertar_d_ordenes(engine_src, [{**ORDEN_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_ordenes_compra", 1, "2026-05-20 14:00:00")
        _proc_ordenes_compra(dry_run=False)
        run = ultimo_run(engine_dst, "r_ordenes_compra")
        assert run["estado"] == "ok"
        assert "2026-05-20" in str(run["watermark"])
