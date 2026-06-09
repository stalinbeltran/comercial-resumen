"""
Tests end-to-end del procesador r_facturas_detalle.
Estrategia: incremental — solo registros nuevos (append-only, watermark en updated_at).
"""
import pytest
from sqlalchemy import text

from etl.pipeline import _proc_facturas_detalle
from tests.etl.helpers import (
    insertar_d_detalle, forzar_updated_at, contar, ultimo_run,
    DETALLE_BASE,
)


pytestmark = pytest.mark.pipeline


class TestFacturasDetalleIncremental:

    def test_primera_corrida_carga_todos_los_registros(self, engine_src, engine_dst, patch_engines):
        """
        DADO   3 líneas en d_facturas_detalle
        CUANDO se ejecuta _proc_facturas_detalle por primera vez
        ENTONCES r_facturas_detalle tiene exactamente 3 filas
        """
        insertar_d_detalle(engine_src, [
            {**DETALLE_BASE, "id": 1, "id_factura": 1},
            {**DETALLE_BASE, "id": 2, "id_factura": 1},
            {**DETALLE_BASE, "id": 3, "id_factura": 2},
        ])

        filas = _proc_facturas_detalle(dry_run=False)

        assert filas == 3
        assert contar(engine_dst, "r_facturas_detalle") == 3

    def test_segunda_corrida_sin_nuevos_no_inserta(self, engine_src, engine_dst, patch_engines):
        """
        DADO   watermark ya posicionado después de la primera corrida
        CUANDO no hay nuevas líneas
        ENTONCES la segunda corrida retorna 0 filas y el destino no cambia
        """
        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 1}])
        _proc_facturas_detalle(dry_run=False)
        filas_segunda = _proc_facturas_detalle(dry_run=False)

        assert filas_segunda == 0
        assert contar(engine_dst, "r_facturas_detalle") == 1

    def test_solo_inserta_registros_post_watermark(self, engine_src, engine_dst, patch_engines):
        """
        DADO   2 registros: uno viejo (antes del watermark) y uno nuevo
        CUANDO se ejecuta el procesador con el watermark ya avanzado
        ENTONCES solo el registro nuevo llega al destino
        """
        insertar_d_detalle(engine_src, [
            {**DETALLE_BASE, "id": 1},
            {**DETALLE_BASE, "id": 2, "numero_factura": "F-002"},
        ])
        forzar_updated_at(engine_src, "d_facturas_detalle", 1, "2026-01-01 08:00:00")
        forzar_updated_at(engine_src, "d_facturas_detalle", 2, "2026-01-01 08:00:00")
        _proc_facturas_detalle(dry_run=False)

        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 3, "id_factura": 3}])
        filas = _proc_facturas_detalle(dry_run=False)

        assert filas == 1
        assert contar(engine_dst, "r_facturas_detalle") == 3

    def test_registro_con_updated_at_igual_watermark_no_se_reprocesa(
        self, engine_src, engine_dst, patch_engines
    ):
        """
        El extractor usa updated_at > watermark (estricto, no >=).
        Un registro con updated_at exactamente igual al watermark no debe reprocesarse.
        """
        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas_detalle", 1, "2026-03-01 10:00:00")
        _proc_facturas_detalle(dry_run=False)

        filas_segunda = _proc_facturas_detalle(dry_run=False)
        assert filas_segunda == 0

    def test_acumula_sin_truncar_en_sucesivas_corridas(self, engine_src, engine_dst, patch_engines):
        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas_detalle", 1, "2026-01-15 10:00:00")
        _proc_facturas_detalle(dry_run=False)
        assert contar(engine_dst, "r_facturas_detalle") == 1

        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 2}])
        forzar_updated_at(engine_src, "d_facturas_detalle", 2, "2030-01-01 00:00:00")
        _proc_facturas_detalle(dry_run=False)
        assert contar(engine_dst, "r_facturas_detalle") == 2

    def test_dry_run_no_escribe(self, engine_src, engine_dst, patch_engines):
        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 1}])
        _proc_facturas_detalle(dry_run=True)
        assert contar(engine_dst, "r_facturas_detalle") == 0

    def test_etl_runs_ok_con_watermark(self, engine_src, engine_dst, patch_engines):
        insertar_d_detalle(engine_src, [{**DETALLE_BASE, "id": 1}])
        _proc_facturas_detalle(dry_run=False)
        run = ultimo_run(engine_dst, "r_facturas_detalle")
        assert run["estado"] == "ok"
        assert run["watermark"] is not None
        assert run["watermark"] != "1900-01-01 00:00:00"
