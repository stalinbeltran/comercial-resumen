"""
Tests de integración de etl/control.py.
Verifican la tabla etl_runs: auditoría, watermarks y estados.
"""
import pytest
from datetime import datetime

import etl.control as control
from tests.etl.helpers import contar, ultimo_run

pytestmark = pytest.mark.integration


class TestRegistrarInicio:

    def test_crea_fila_con_estado_running(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["estado"] == "running"
        assert run["id"] == run_id

    def test_retorna_id_autoincremental(self, engine_dst, patch_engines):
        id1 = control.registrar_inicio("r_facturas")
        id2 = control.registrar_inicio("r_facturas")
        assert id2 > id1

    def test_registra_tabla_correcta(self, engine_dst, patch_engines):
        control.registrar_inicio("r_inventario")
        run = ultimo_run(engine_dst, "r_inventario")
        assert run["tabla"] == "r_inventario"

    def test_fin_y_watermark_son_nulos_al_inicio(self, engine_dst, patch_engines):
        control.registrar_inicio("r_facturas")
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["fin"] is None
        assert run["watermark"] is None


class TestRegistrarFin:

    def test_estado_ok_con_filas_y_watermark(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 42, watermark="2026-03-15 10:00:00")
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["estado"] == "ok"
        assert run["filas"] == 42
        assert "2026-03-15" in str(run["watermark"])

    def test_estado_ok_con_cero_filas(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 0, watermark="2026-01-01 00:00:00")
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["estado"] == "ok"
        assert run["filas"] == 0

    def test_estado_error_con_mensaje(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 0, error="conexión rechazada")
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["estado"] == "error"
        assert "conexión rechazada" in run["mensaje"]

    def test_fin_se_registra_como_datetime(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 10, watermark="2026-01-01 00:00:00")
        run = ultimo_run(engine_dst, "r_facturas")
        assert isinstance(run["fin"], datetime)

    def test_watermark_nulo_cuando_no_aplica(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_inventario")
        control.registrar_fin(run_id, "r_inventario", 5, watermark=None)
        run = ultimo_run(engine_dst, "r_inventario")
        assert run["watermark"] is None
        assert run["estado"] == "ok"


class TestGetWatermark:

    def test_retorna_1900_sin_corridas_previas(self, engine_dst, patch_engines):
        wm = control.get_watermark("r_tabla_sin_historial")
        assert wm == "1900-01-01 00:00:00"

    def test_retorna_watermark_de_ultima_corrida_ok(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 10, watermark="2026-03-01 08:00:00")
        wm = control.get_watermark("r_facturas")
        assert "2026-03-01" in wm

    def test_ignora_corridas_con_error(self, engine_dst, patch_engines):
        run_id = control.registrar_inicio("r_facturas")
        control.registrar_fin(run_id, "r_facturas", 0, error="fallo grave")
        wm = control.get_watermark("r_facturas")
        assert wm == "1900-01-01 00:00:00"

    def test_retorna_el_mas_reciente_entre_varias_corridas_ok(self, engine_dst, patch_engines):
        r1 = control.registrar_inicio("r_facturas")
        control.registrar_fin(r1, "r_facturas", 5, watermark="2026-01-01 00:00:00")
        r2 = control.registrar_inicio("r_facturas")
        control.registrar_fin(r2, "r_facturas", 3, watermark="2026-06-01 00:00:00")
        wm = control.get_watermark("r_facturas")
        assert "2026-06-01" in wm

    def test_no_mezcla_watermarks_entre_tablas(self, engine_dst, patch_engines):
        r1 = control.registrar_inicio("r_facturas")
        control.registrar_fin(r1, "r_facturas", 10, watermark="2026-05-01 00:00:00")
        wm_ordenes = control.get_watermark("r_ordenes_compra")
        assert wm_ordenes == "1900-01-01 00:00:00"
