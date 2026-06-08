"""
Tests de reportes gerenciales.

Cubre:
  - Top N productos más vendidos (orden y límite)
  - Comparativo de períodos (mes actual vs. anterior)
  - Margen bruto por producto
  - Sin ventas: resultado vacío sin error
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixture compartida
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_ventas_gerencial(db_connection, seed_base, seed_terceros):
    """
    Producto 1: 100 unidades vendidas ($2000) — debe ser el top 1
    Producto 2:  30 unidades vendidas  ($600) — debe ser el top 2
    Período: enero 2025
    """
    cur = db_connection.cursor()

    # Factura enero con dos productos
    cur.execute("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, subtotal, descuento, impuesto, total, saldo)
        VALUES (901, 901, 901, 'FG-001', '2025-01-10', '2025-02-10',
                'activa', 2321.43, 0, 278.57, 2600.00, 2600.00)
    """)
    detalles = [
        (901, 901, 901, 901, 901, 100.0000, 20.00, 0, 2000.00, 8.00),
        (902, 901, 902, 902, 901,  30.0000, 20.00, 0,  600.00, 8.00),
    ]
    cur.executemany("""
        INSERT INTO facturas_detalle
            (id, id_factura, id_producto, id_presentacion, id_bodega,
             cantidad, precio_unitario, descuento, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, detalles)

    # Factura diciembre anterior (para comparativo)
    cur.execute("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, subtotal, descuento, impuesto, total, saldo)
        VALUES (902, 901, 901, 'FG-002', '2024-12-15', '2025-01-15',
                'activa', 892.86, 0, 107.14, 1000.00, 1000.00)
    """)
    cur.execute("""
        INSERT INTO facturas_detalle
            (id, id_factura, id_producto, id_presentacion, id_bodega,
             cantidad, precio_unitario, descuento, subtotal, costo_unitario)
        VALUES (903, 902, 901, 901, 901, 50.0000, 20.00, 0, 1000.00, 8.00)
    """)
    cur.close()
    return {**seed_base, **seed_terceros}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTopProductos:

    def test_top_1_es_producto_con_mayor_cantidad(self, db_connection, seed_ventas_gerencial):
        """
        DADO Producto 1 con 100 und y Producto 2 con 30 und
        CUANDO se pide top 1
        ENTONCES solo aparece Producto 1.
        """
        resultado = ejecutar_reporte(
            db_connection, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 1)
        )
        assert len(resultado) == 1
        assert resultado[0]["codigo_producto"] == "PROD-T01"

    def test_top_2_incluye_ambos_en_orden(self, db_connection, seed_ventas_gerencial):
        """Top 2 debe retornar Producto 1 primero, Producto 2 segundo."""
        resultado = ejecutar_reporte(
            db_connection, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 2)
        )
        assert len(resultado) == 2
        assert resultado[0]["codigo_producto"] == "PROD-T01"
        assert resultado[1]["codigo_producto"] == "PROD-T02"

    def test_totales_de_unidades_correctos(self, db_connection, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            db_connection, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 10)
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-T01"]["total_unidades"] == Decimal("100.0000")
        assert por_codigo["PROD-T02"]["total_unidades"] == Decimal("30.0000")

    def test_totales_de_venta_correctos(self, db_connection, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            db_connection, "top_productos_vendidos.sql",
            ("2025-01-01", "2025-01-31", 10)
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-T01"]["total_venta"] == Decimal("2000.00")
        assert por_codigo["PROD-T02"]["total_venta"] == Decimal("600.00")

    def test_periodo_sin_ventas_retorna_vacio(self, db_connection, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            db_connection, "top_productos_vendidos.sql",
            ("2023-01-01", "2023-01-31", 10)
        )
        assert resultado == []


class TestComparativoPeriodos:

    def test_enero_mayor_que_diciembre(self, db_connection, seed_ventas_gerencial):
        """
        Enero 2025: $2600 vs Diciembre 2024: $1000 → crecimiento positivo
        """
        sql_periodo = """
            SELECT SUM(f.total) AS total
            FROM facturas f
            WHERE f.deleted_at IS NULL
              AND f.estado <> 'anulada'
              AND f.fecha_emision BETWEEN %s AND %s
        """
        enero = ejecutar_query(db_connection, sql_periodo, ("2025-01-01", "2025-01-31"))
        dic   = ejecutar_query(db_connection, sql_periodo, ("2024-12-01", "2024-12-31"))
        assert enero[0]["total"] > dic[0]["total"]

    def test_totales_por_periodo(self, db_connection, seed_ventas_gerencial):
        sql_periodo = """
            SELECT SUM(f.total) AS total
            FROM facturas f
            WHERE f.deleted_at IS NULL
              AND f.estado <> 'anulada'
              AND f.fecha_emision BETWEEN %s AND %s
        """
        enero = ejecutar_query(db_connection, sql_periodo, ("2025-01-01", "2025-01-31"))
        dic   = ejecutar_query(db_connection, sql_periodo, ("2024-12-01", "2024-12-31"))
        assert enero[0]["total"] == Decimal("2600.00")
        assert dic[0]["total"]   == Decimal("1000.00")


class TestMargenBruto:

    def test_margen_por_producto_calculado(self, db_connection, seed_ventas_gerencial):
        """
        Producto 1: venta=$2000, costo=100×8=$800 → margen=$1200
        Producto 2: venta=$600,  costo=30×8=$240  → margen=$360
        """
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-T01"]["margen_bruto"] == Decimal("1200.00")
        assert por_codigo["PROD-T02"]["margen_bruto"] == Decimal("360.00")

    def test_margen_positivo_en_todos_los_productos(self, db_connection, seed_ventas_gerencial):
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        for r in resultado:
            assert r["margen_bruto"] > 0
