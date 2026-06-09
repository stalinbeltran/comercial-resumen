"""
Tests end-to-end del procesador r_facturas.
Estrategia: UPSERT — estado y saldo pueden cambiar en registros ya cargados.
"""
import pytest
from sqlalchemy import text

from etl.pipeline import _proc_facturas
from tests.etl.helpers import (
    insertar_d_facturas, forzar_updated_at, contar, leer_campo, ultimo_run,
    FACTURA_BASE,
)

pytestmark = pytest.mark.pipeline


class TestFacturasUpsert:

    def test_primera_corrida_carga_todas_las_facturas(self, engine_src, engine_dst, patch_engines):
        """
        DADO   3 facturas en d_facturas
        CUANDO se ejecuta _proc_facturas por primera vez
        ENTONCES r_facturas tiene exactamente 3 filas
        """
        insertar_d_facturas(engine_src, [
            {**FACTURA_BASE, "id": 1, "numero_factura": "F-001"},
            {**FACTURA_BASE, "id": 2, "numero_factura": "F-002"},
            {**FACTURA_BASE, "id": 3, "numero_factura": "F-003"},
        ])

        filas = _proc_facturas(dry_run=False)

        assert filas == 3
        assert contar(engine_dst, "r_facturas") == 3

    def test_segunda_corrida_sin_cambios_no_duplica(self, engine_src, engine_dst, patch_engines):
        """
        DADO   watermark ya avanzado después de la primera corrida
        CUANDO se ejecuta una segunda corrida sin nuevas facturas
        ENTONCES r_facturas sigue con el mismo número de filas
        """
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        _proc_facturas(dry_run=False)
        filas_segunda = _proc_facturas(dry_run=False)

        assert filas_segunda == 0
        assert contar(engine_dst, "r_facturas") == 1

    def test_upsert_actualiza_saldo_en_factura_existente(self, engine_src, engine_dst, patch_engines):
        """
        DADO   r_facturas con factura id=1 con saldo=500
        CUANDO d_facturas.saldo cambia a 0 y updated_at avanza
        ENTONCES r_facturas.saldo queda en 0
        """
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1, "saldo": 500.00}])
        _proc_facturas(dry_run=False)

        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_facturas SET saldo = 0.00, updated_at = '2030-01-01 00:00:00' WHERE id = 1"
            ))
        _proc_facturas(dry_run=False)

        saldo = leer_campo(engine_dst, "r_facturas", "saldo",
                           "id_factura_orig = :id", {"id": 1})
        assert float(saldo) == 0.00

    def test_upsert_actualiza_estado_pendiente_a_pagada(self, engine_src, engine_dst, patch_engines):
        """
        DADO   factura en estado 'pendiente'
        CUANDO cambia a 'pagada' en la fuente
        ENTONCES r_facturas refleja el nuevo estado
        """
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1, "estado": "pendiente"}])
        _proc_facturas(dry_run=False)

        with engine_src.begin() as conn:
            conn.execute(text(
                "UPDATE d_facturas SET estado = 'pagada', updated_at = '2030-01-01 00:00:00' WHERE id = 1"
            ))
        _proc_facturas(dry_run=False)

        estado = leer_campo(engine_dst, "r_facturas", "estado",
                            "id_factura_orig = :id", {"id": 1})
        assert estado == "pagada"

    def test_watermark_no_reprocesa_facturas_sin_cambios(self, engine_src, engine_dst, patch_engines):
        insertar_d_facturas(engine_src, [
            {**FACTURA_BASE, "id": 1},
            {**FACTURA_BASE, "id": 2, "numero_factura": "F-002"},
        ])
        forzar_updated_at(engine_src, "d_facturas", 1, "2026-01-01 08:00:00")
        forzar_updated_at(engine_src, "d_facturas", 2, "2026-01-01 08:00:00")
        _proc_facturas(dry_run=False)

        filas_segunda = _proc_facturas(dry_run=False)
        assert filas_segunda == 0

    def test_dry_run_no_escribe(self, engine_src, engine_dst, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        _proc_facturas(dry_run=True)
        assert contar(engine_dst, "r_facturas") == 0

    def test_etl_runs_registra_watermark_correcto(self, engine_src, engine_dst, patch_engines):
        insertar_d_facturas(engine_src, [{**FACTURA_BASE, "id": 1}])
        forzar_updated_at(engine_src, "d_facturas", 1, "2026-04-15 09:00:00")
        _proc_facturas(dry_run=False)
        run = ultimo_run(engine_dst, "r_facturas")
        assert run["estado"] == "ok"
        assert "2026-04-15" in str(run["watermark"])
