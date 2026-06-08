"""
Tests de integración E2E para tesorería.

Flujo: facturas en DB normalizada → ETL (d_facturas) → asserts de CxC en desnormalizada.
"""
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query
from db.importar_desnormalizada import importar_tabla


class TestCuentasPorCobrarIntegracion:
    FECHA_CORTE = "2025-03-01"

    def _run(self, dst_conn):
        return ejecutar_reporte(
            dst_conn, "cuentas_por_cobrar.sql",
            (self.FECHA_CORTE,) * 6
        )

    def test_excluye_facturas_pagadas(self, dst_conn, seed_cxc):
        """F-PAG (estado=pagada, saldo=0) no debe aparecer en d_facturas tras el ETL."""
        resultado = self._run(dst_conn)
        numeros = [r["numero"] for r in resultado]
        assert "F-PAG" not in numeros

    def test_total_facturas_pendientes(self, dst_conn, seed_cxc):
        """Deben aparecer 5 facturas con saldo > 0."""
        resultado = self._run(dst_conn)
        assert len(resultado) == 5

    def test_rango_vigente(self, dst_conn, seed_cxc):
        """F-VIG vence 2025-03-15 → no vencida al corte → 'vigente'."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-VIG"]["rango_antiguedad"] == "vigente"

    def test_rango_1_30(self, dst_conn, seed_cxc):
        """F-030 vence 2025-02-10 → 19 días vencida al corte → '1-30'."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-030"]["rango_antiguedad"] == "1-30"

    def test_rango_31_60(self, dst_conn, seed_cxc):
        """F-060 vence 2025-01-20 → 40 días vencida al corte → '31-60'."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-060"]["rango_antiguedad"] == "31-60"

    def test_rango_61_90(self, dst_conn, seed_cxc):
        """F-090 vence 2024-12-30 → 61 días vencida al corte → '61-90'."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-090"]["rango_antiguedad"] == "61-90"

    def test_rango_mas_90(self, dst_conn, seed_cxc):
        """F-MAS vence 2024-11-01 → 120 días vencida al corte → '+90'."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-MAS"]["rango_antiguedad"] == "+90"

    def test_saldo_correcto(self, dst_conn, seed_cxc):
        """El saldo importado por el ETL debe coincidir con el de la normalizada."""
        por_numero = {r["numero"]: r for r in self._run(dst_conn)}
        assert por_numero["F-VIG"]["saldo"] == Decimal("500.00")
        assert por_numero["F-MAS"]["saldo"] == Decimal("100.00")

    def test_etl_excluye_facturas_soft_deleted(self, src_conn, dst_conn, seed_cxc):
        """Re-ejecutar el ETL tras soft-delete en normalizada excluye la factura de d_facturas."""
        cur = src_conn.cursor()
        cur.execute("UPDATE facturas SET deleted_at = NOW() WHERE id = 801")
        src_conn.commit()
        cur.close()

        importar_tabla(src_conn, dst_conn, "d_facturas", batch_size=500)

        resultado = self._run(dst_conn)
        numeros = [r["numero"] for r in resultado]
        assert "F-VIG" not in numeros
        assert len(resultado) == 4
