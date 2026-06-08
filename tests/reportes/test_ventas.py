"""
Tests del módulo de Ventas.

Cubre:
  - Ventas por período (total, filtro de fechas, filtro de sucursal)
  - Ventas por producto (ranking, margen)
  - Facturas anuladas excluidas
  - Caso borde: período sin ventas
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_facturas(db_connection, seed_base, seed_terceros):
    """
    3 facturas en enero 2025, 1 factura en febrero 2025, 1 anulada en enero.
      F-001  cliente 901  sucursal 901  total=100.00  enero
      F-002  cliente 901  sucursal 901  total=200.00  enero
      F-003  cliente 901  sucursal 901  total=300.00  enero
      F-004  cliente 901  sucursal 901  total=999.00  febrero
      F-ANU  cliente 901  sucursal 901  total=500.00  enero  estado=anulada
    """
    cur = db_connection.cursor()
    facturas = [
        (901, 901, 901, 'F-001', '2025-01-10', '2025-02-10', 'activa',  89.29, 0, 10.71, 100.00, 100.00),
        (902, 901, 901, 'F-002', '2025-01-15', '2025-02-15', 'activa', 178.57, 0, 21.43, 200.00, 200.00),
        (903, 901, 901, 'F-003', '2025-01-20', '2025-02-20', 'activa', 267.86, 0, 32.14, 300.00, 300.00),
        (904, 901, 901, 'F-004', '2025-02-05', '2025-03-05', 'activa', 891.96, 0, 107.04, 999.00, 999.00),
        (905, 901, 901, 'F-ANU', '2025-01-25', '2025-02-25', 'anulada', 446.43, 0, 53.57, 500.00, 500.00),
    ]
    cur.executemany("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, subtotal, descuento, impuesto, total, saldo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, facturas)
    cur.close()
    return {**seed_base, **seed_terceros}


@pytest.fixture
def seed_facturas_con_detalle(db_connection, seed_facturas):
    """Agrega detalle a F-001, F-002, F-003 para test de ventas_por_producto."""
    cur = db_connection.cursor()
    detalles = [
        # id, id_factura, id_producto, id_presentacion, id_bodega, cantidad, precio_unit, descuento, subtotal, costo_unit
        (901, 901, 901, 901, 901, 5.0000, 20.00, 0, 100.00, 10.00),
        (902, 902, 901, 901, 901, 10.0000, 20.00, 0, 200.00, 10.00),
        (903, 903, 902, 902, 901, 15.0000, 20.00, 0, 300.00, 10.00),
    ]
    cur.executemany("""
        INSERT INTO facturas_detalle
            (id, id_factura, id_producto, id_presentacion, id_bodega,
             cantidad, precio_unitario, descuento, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, detalles)
    cur.close()
    return seed_facturas


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVentasPorPeriodo:

    def test_total_enero_tres_facturas(self, db_connection, seed_facturas):
        """
        DADO 3 facturas activas en enero + 1 anulada
        CUANDO se consulta enero 2025
        ENTONCES retorna 3 facturas con total=600.00
        """
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        assert len(resultado) == 3
        total = sum(r["total"] for r in resultado)
        assert total == Decimal("600.00")

    def test_facturas_anuladas_excluidas(self, db_connection, seed_facturas):
        """La factura anulada F-ANU no debe aparecer en los resultados."""
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        numeros = [r["numero_factura"] for r in resultado]
        assert "F-ANU" not in numeros

    def test_filtro_sucursal_solo_devuelve_esa_sucursal(self, db_connection, seed_facturas):
        """Filtrar por sucursal 901 retorna las mismas 3 facturas."""
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", 901, 901)
        )
        assert len(resultado) == 3

    def test_filtro_fecha_excluye_febrero(self, db_connection, seed_facturas):
        """La factura F-004 de febrero no debe aparecer al filtrar solo enero."""
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        numeros = [r["numero_factura"] for r in resultado]
        assert "F-004" not in numeros

    def test_periodo_sin_facturas_retorna_vacio(self, db_connection, seed_facturas):
        """Un período sin facturas debe retornar lista vacía."""
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2024-01-01", "2024-01-31", None, None)
        )
        assert resultado == []

    def test_totales_individuales_correctos(self, db_connection, seed_facturas):
        """Cada factura debe tener el total exacto insertado."""
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_periodo.sql",
            ("2025-01-01", "2025-01-31", None, None)
        )
        totales = {r["numero_factura"]: r["total"] for r in resultado}
        assert totales["F-001"] == Decimal("100.00")
        assert totales["F-002"] == Decimal("200.00")
        assert totales["F-003"] == Decimal("300.00")


class TestVentasPorProducto:

    def test_ranking_correcto(self, db_connection, seed_facturas_con_detalle):
        """
        Producto 1: 15 und × $20 = $300 total (F-001 + F-002)
        Producto 2: 15 und × $20 = $300 total (F-003)
        Ambos deben aparecer con sus totales.
        """
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert len(resultado) == 2
        por_codigo = {r["codigo_producto"]: r for r in resultado}
        assert por_codigo["PROD-T01"]["total_venta"] == Decimal("300.00")
        assert por_codigo["PROD-T02"]["total_venta"] == Decimal("300.00")

    def test_margen_bruto_calculado(self, db_connection, seed_facturas_con_detalle):
        """
        Producto 1: venta=300, costo=15×10=150 → margen=150
        Producto 2: venta=300, costo=15×10=150 → margen=150
        """
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_producto.sql",
            ("2025-01-01", "2025-01-31")
        )
        for r in resultado:
            assert r["margen_bruto"] == Decimal("150.00")

    def test_periodo_sin_ventas_retorna_vacio(self, db_connection, seed_facturas_con_detalle):
        resultado = ejecutar_reporte(
            db_connection, "ventas_por_producto.sql",
            ("2024-01-01", "2024-01-31")
        )
        assert resultado == []
