"""
Tests end-to-end del procesador r_movimientos_inventario.
Estrategia: incremental — append-only por naturaleza, watermark en updated_at.
"""
import pytest
from sqlalchemy import text

from etl.pipeline import _proc_movimientos
from tests.etl.helpers import (
    insertar_d_movimientos, forzar_updated_at, contar, leer_campo, ultimo_run,
    MOVIMIENTO_BASE,
)

pytestmark = pytest.mark.pipeline


class TestMovimientosIncremental:

    def test_primera_corrida_carga_todos_los_movimientos(self, engine_src, engine_dst, patch_engines):
        """
        DADO   5 movimientos en d_movimientos_inventario
        CUANDO se ejecuta _proc_movimientos por primera vez
        ENTONCES r_movimientos_inventario tiene exactamente 5 filas
        """
        movimientos = [{**MOVIMIENTO_BASE} for _ in range(5)]
        insertar_d_movimientos(engine_src, movimientos)

        filas = _proc_movimientos(dry_run=False)

        assert filas == 5
        assert contar(engine_dst, "r_movimientos_inventario") == 5

    def test_segunda_corrida_sin_nuevos_retorna_cero(self, engine_src, engine_dst, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        _proc_movimientos(dry_run=False)
        filas_segunda = _proc_movimientos(dry_run=False)

        assert filas_segunda == 0
        assert contar(engine_dst, "r_movimientos_inventario") == 1

    def test_solo_carga_movimientos_post_watermark(self, engine_src, engine_dst, patch_engines):
        """
        DADO   2 movimientos anteriores ya procesados y 1 nuevo
        CUANDO se ejecuta el procesador
        ENTONCES solo el nuevo llega al destino (total = 3, pero corrida = 1)
        """
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE, MOVIMIENTO_BASE])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_movimientos_inventario SET updated_at = '2026-01-01 00:00:00'"
            ))
        _proc_movimientos(dry_run=False)
        assert contar(engine_dst, "r_movimientos_inventario") == 2

        insertar_d_movimientos(engine_src, [{**MOVIMIENTO_BASE, "tipo_movimiento": "salida"}])
        filas = _proc_movimientos(dry_run=False)

        assert filas == 1
        assert contar(engine_dst, "r_movimientos_inventario") == 3

    def test_movimiento_deleted_at_en_fuente_no_llega_a_destino(
        self, engine_src, engine_dst, patch_engines
    ):
        """
        Los movimientos son append-only pero pueden tener deleted_at.
        El extractor filtra deleted_at IS NULL en la fuente.
        """
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_movimientos_inventario "
                "SET deleted_at = NOW(), updated_at = NOW()"
            ))

        filas = _proc_movimientos(dry_run=False)

        assert filas == 0
        assert contar(engine_dst, "r_movimientos_inventario") == 0

    def test_tipo_movimiento_preservado_correctamente(self, engine_src, engine_dst, patch_engines):
        insertar_d_movimientos(engine_src, [{**MOVIMIENTO_BASE, "tipo_movimiento": "traslado"}])
        _proc_movimientos(dry_run=False)
        tipo = leer_campo(
            engine_dst, "r_movimientos_inventario", "tipo_movimiento",
            "1=1 LIMIT 1", {}
        )
        assert tipo == "traslado"

    def test_dry_run_no_escribe(self, engine_src, engine_dst, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        _proc_movimientos(dry_run=True)
        assert contar(engine_dst, "r_movimientos_inventario") == 0

    def test_etl_runs_registra_estado_ok(self, engine_src, engine_dst, patch_engines):
        insertar_d_movimientos(engine_src, [MOVIMIENTO_BASE])
        _proc_movimientos(dry_run=False)
        run = ultimo_run(engine_dst, "r_movimientos_inventario")
        assert run["estado"] == "ok"
        assert run["filas"] == 1
