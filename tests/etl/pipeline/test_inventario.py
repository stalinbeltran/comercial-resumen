"""
Tests end-to-end del procesador r_inventario.
Estrategia: full reload — TRUNCATE + INSERT en cada corrida.
"""
import pytest
from sqlalchemy import text

from etl.pipeline import _proc_inventario
from tests.etl.helpers import (
    insertar_d_inventario, contar, leer_tabla, ultimo_run,
    INVENTARIO_BASE,
)

pytestmark = pytest.mark.pipeline


class TestInventarioFullReload:

    def test_primera_corrida_carga_todas_las_filas(self, engine_src, engine_dst, patch_engines):
        """
        DADO   3 filas en d_inventario
        CUANDO se ejecuta _proc_inventario
        ENTONCES r_inventario tiene exactamente 3 filas
        """
        filas_src = [
            {**INVENTARIO_BASE, "id_producto": 1},
            {**INVENTARIO_BASE, "id_producto": 2},
            {**INVENTARIO_BASE, "id_producto": 3},
        ]
        insertar_d_inventario(engine_src, filas_src)

        filas = _proc_inventario(dry_run=False)

        assert filas == 3
        assert contar(engine_dst, "r_inventario") == 3

    def test_segunda_corrida_no_duplica_filas(self, engine_src, engine_dst, patch_engines):
        """
        DADO   2 filas en fuente
        CUANDO se ejecuta el procesador dos veces consecutivas
        ENTONCES r_inventario sigue con exactamente 2 filas (no 4)
        """
        insertar_d_inventario(engine_src, [
            {**INVENTARIO_BASE, "id_producto": 1},
            {**INVENTARIO_BASE, "id_producto": 2},
        ])
        _proc_inventario(dry_run=False)
        filas = _proc_inventario(dry_run=False)

        assert contar(engine_dst, "r_inventario") == 2

    def test_fuente_vacia_trunca_destino(self, engine_src, engine_dst, patch_engines):
        """
        DADO   destino con datos de una corrida anterior y fuente vacía
        CUANDO se ejecuta el procesador
        ENTONCES r_inventario queda vacío
        """
        insertar_d_inventario(engine_src, [{**INVENTARIO_BASE, "id_producto": 1}])
        _proc_inventario(dry_run=False)
        assert contar(engine_dst, "r_inventario") == 1

        with engine_src.begin() as conn:
            conn.execute(text("TRUNCATE TABLE d_inventario"))
        _proc_inventario(dry_run=False)

        assert contar(engine_dst, "r_inventario") == 0

    def test_filas_con_deleted_at_no_pasan_al_destino(self, engine_src, engine_dst, patch_engines):
        """
        DADO   1 fila activa y 1 fila con deleted_at en fuente
        CUANDO se ejecuta el procesador
        ENTONCES r_inventario tiene solo 1 fila
        """
        insertar_d_inventario(engine_src, [
            {**INVENTARIO_BASE, "id_producto": 1},
            {**INVENTARIO_BASE, "id_producto": 2},
        ])
        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_inventario SET deleted_at = NOW() WHERE id_producto = 2"
            ))

        _proc_inventario(dry_run=False)

        assert contar(engine_dst, "r_inventario") == 1

    def test_dry_run_no_escribe_en_destino(self, engine_src, engine_dst, patch_engines):
        insertar_d_inventario(engine_src, [{**INVENTARIO_BASE, "id_producto": 1}])
        _proc_inventario(dry_run=True)
        assert contar(engine_dst, "r_inventario") == 0

    def test_etl_runs_registra_corrida_ok(self, engine_src, engine_dst, patch_engines):
        insertar_d_inventario(engine_src, [{**INVENTARIO_BASE, "id_producto": 1}])
        _proc_inventario(dry_run=False)
        run = ultimo_run(engine_dst, "r_inventario")
        assert run["estado"] == "ok"
        assert run["filas"] == 1
        assert run["fin"] is not None
