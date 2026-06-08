"""
Tests de integración E2E para ventas.

Flujo: facturas en DB normalizada → ETL (d_facturas, d_facturas_detalle) → asserts en desnormalizada.
"""
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query
from db.importar_desnormalizada import importar_tabla


class TestVentasPorPeriodoIntegracion:

    def test_total_enero_tres_facturas(self, dst_conn, seed_facturas):
        """
        DADO 3 facturas activas en enero en DB normalizada
        CUANDO el ETL importa d_facturas
        ENTONCES retorna 3 facturas con total=600.00 en la desnormalizada
        """
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        assert len(resultado) == 3
        total = sum(r["total"] for r in resultado)
        assert total == Decimal("600.00")

    def test_facturas_anuladas_excluidas(self, dst_conn, seed_facturas):
        """F-ANU (anulada) existe en d_facturas pero la query la excluye."""
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        numeros = [r["numero_factura"] for r in resultado]
        assert "F-ANU" not in numeros

    def test_filtro_sucursal(self, dst_conn, seed_facturas):
        """Filtrar por sucursal 801 retorna las mismas 3 facturas de enero."""
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", 801, 801)
        )
        assert len(resultado) == 3

    def test_filtro_fecha_excluye_febrero(self, dst_conn, seed_facturas):
        """F-I04 de febrero no aparece al filtrar solo enero."""
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        numeros = [r["numero_factura"] for r in resultado]
        assert "F-I04" not in numeros

    def test_periodo_sin_facturas_retorna_vacio(self, dst_conn, seed_facturas):
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2024-01-01", "2024-01-31", None, None)
        )
        assert resultado == []

    def test_totales_individuales_correctos(self, dst_conn, seed_facturas):
        """Cada factura debe tener el total exacto insertado en la normalizada."""
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        totales = {r["numero_factura"]: r["total"] for r in resultado}
        assert totales["F-I01"] == Decimal("100.00")
        assert totales["F-I02"] == Decimal("200.00")
        assert totales["F-I03"] == Decimal("300.00")

    def test_etl_excluye_facturas_soft_deleted(self, src_conn, dst_conn, seed_facturas):
        """El ETL usa WHERE deleted_at IS NULL; re-ejecutar después de soft-delete excluye la factura."""
        cur = src_conn.cursor()
        cur.execute("UPDATE facturas SET deleted_at = NOW() WHERE id = 801")
        src_conn.commit()
        cur.close()

        importar_tabla(src_conn, dst_conn, "d_facturas", batch_size=500)

        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        assert len(resultado) == 2
        numeros = [r["numero_factura"] for r in resultado]
        assert "F-I01" not in numeros


class TestVentasPorProductoIntegracion:

    def test_ranking_correcto(self, dst_conn, seed_facturas_con_detalle):
        """
        Prod 801: 15 und × $20 = $300 (F-I01 + F-I02)
        Prod 802: 15 und × $20 = $300 (F-I03)
        """
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert len(resultado) == 2
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-I01"]["total_venta"] == Decimal("300.00")
        assert por_codigo["PROD-I02"]["total_venta"] == Decimal("300.00")

    def test_margen_bruto_calculado(self, dst_conn, seed_facturas_con_detalle):
        """
        Prod 801: venta=300, costo=15×10=150 → margen=150
        Prod 802: venta=300, costo=15×10=150 → margen=150
        """
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        for r in resultado:
            assert r["margen_bruto"] == Decimal("150.00")

    def test_periodo_sin_ventas_retorna_vacio(self, dst_conn, seed_facturas_con_detalle):
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_producto.sql",
            ("2024-01-01", "2024-01-31")
        )
        assert resultado == []
