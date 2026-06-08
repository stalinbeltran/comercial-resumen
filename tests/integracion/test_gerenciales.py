"""
Tests de integración E2E para reportes gerenciales.

Flujo: facturas + detalle en DB normalizada → ETL (d_facturas, d_facturas_detalle)
       → asserts en desnormalizada.
"""
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


class TestTopProductosIntegracion:

    def test_top_1_es_producto_con_mayor_cantidad(self, dst_conn, seed_ventas_gerencial):
        """
        DADO prod 801 con 100 und y prod 802 con 30 und
        CUANDO el ETL importa d_facturas_detalle y se pide top 1
        ENTONCES solo aparece prod 801
        """
        resultado = ejecutar_reporte(
            dst_conn, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 1)
        )
        assert len(resultado) == 1
        assert resultado[0]["codigo_producto"] == "PROD-I01"

    def test_top_2_incluye_ambos_en_orden(self, dst_conn, seed_ventas_gerencial):
        """Top 2: prod 801 primero (mayor unidades), prod 802 segundo."""
        resultado = ejecutar_reporte(
            dst_conn, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 2)
        )
        assert len(resultado) == 2
        assert resultado[0]["codigo_producto"] == "PROD-I01"
        assert resultado[1]["codigo_producto"] == "PROD-I02"

    def test_totales_de_unidades_correctos(self, dst_conn, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            dst_conn, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 10)
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-I01"]["total_unidades"] == Decimal("100.0000")
        assert por_codigo["PROD-I02"]["total_unidades"] == Decimal("30.0000")

    def test_totales_de_venta_correctos(self, dst_conn, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            dst_conn, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 10)
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-I01"]["total_venta"] == Decimal("2000.00")
        assert por_codigo["PROD-I02"]["total_venta"] == Decimal("600.00")

    def test_periodo_sin_ventas_retorna_vacio(self, dst_conn, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            dst_conn, "top_productos_vendidos.sql",
            ("2023-01-01", "2023-01-31", 10)
        )
        assert resultado == []


class TestComparativoPeriodosIntegracion:

    def test_enero_mayor_que_diciembre(self, dst_conn, seed_ventas_gerencial):
        """
        Enero 2025: $2600 vs Diciembre 2024: $1000.
        Consulta sobre d_facturas (ETL ya importó ambas facturas).
        """
        sql = """
            SELECT SUM(total) AS total
            FROM d_facturas
            WHERE deleted_at IS NULL
              AND estado <> 'anulada'
              AND fecha_emision BETWEEN %s AND %s
        """
        enero = ejecutar_query(dst_conn, sql, ("2025-01-01", "2025-01-31"))
        dic   = ejecutar_query(dst_conn, sql, ("2024-12-01", "2024-12-31"))
        assert enero[0]["total"] > dic[0]["total"]

    def test_totales_por_periodo(self, dst_conn, seed_ventas_gerencial):
        sql = """
            SELECT SUM(total) AS total
            FROM d_facturas
            WHERE deleted_at IS NULL
              AND estado <> 'anulada'
              AND fecha_emision BETWEEN %s AND %s
        """
        enero = ejecutar_query(dst_conn, sql, ("2025-01-01", "2025-01-31"))
        dic   = ejecutar_query(dst_conn, sql, ("2024-12-01", "2024-12-31"))
        assert enero[0]["total"] == Decimal("2600.00")
        assert dic[0]["total"]   == Decimal("1000.00")


class TestMargenBrutoIntegracion:

    def test_margen_por_producto_calculado(self, dst_conn, seed_ventas_gerencial):
        """
        Prod 801: venta=$2000, costo=100×8=$800 → margen=$1200
        Prod 802: venta=$600,  costo=30×8=$240  → margen=$360
        """
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-I01"]["margen_bruto"] == Decimal("1200.00")
        assert por_codigo["PROD-I02"]["margen_bruto"] == Decimal("360.00")

    def test_margen_positivo_en_todos_los_productos(self, dst_conn, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            dst_conn, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        for r in resultado:
            assert r["margen_bruto"] > 0
