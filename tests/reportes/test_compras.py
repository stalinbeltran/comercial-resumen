"""
Tests del módulo de Compras.

Cubre:
  - Órdenes de compra por estado
  - Compras por proveedor (totales y conteo)
  - Órdenes canceladas excluidas
  - Período sin compras
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_ordenes_compra(db_connection, seed_base, seed_terceros):
    """
    3 órdenes aprobadas en enero 2025 + 1 cancelada + 1 en febrero.
      OC-001 proveedor 902  total=500   aprobada   enero
      OC-002 proveedor 902  total=300   aprobada   enero
      OC-003 proveedor 902  total=200   aprobada   enero
      OC-004 proveedor 902  total=999   aprobada   febrero
      OC-CAN proveedor 902  total=100   cancelada  enero
    """
    cur = db_connection.cursor()
    ordenes = [
        (901, 901, 902, 901, 'OC-001', '2025-01-05', 'aprobada', 446.43, 0, 53.57, 500.00),
        (902, 901, 902, 901, 'OC-002', '2025-01-12', 'aprobada', 267.86, 0, 32.14, 300.00),
        (903, 901, 902, 901, 'OC-003', '2025-01-20', 'aprobada', 178.57, 0, 21.43, 200.00),
        (904, 901, 902, 901, 'OC-004', '2025-02-03', 'aprobada', 891.96, 0, 107.04, 999.00),
        (905, 901, 902, 901, 'OC-CAN', '2025-01-08', 'cancelada', 89.29, 0, 10.71, 100.00),
    ]
    cur.executemany("""
        INSERT INTO ordenes_compra
            (id, id_sucursal, id_proveedor, id_bodega_destino, numero, fecha_emision,
             estado, subtotal, descuento, impuesto, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, ordenes)
    cur.close()
    return {**seed_base, **seed_terceros}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComprasPorProveedor:

    def test_total_enero_tres_ordenes(self, db_connection, seed_ordenes_compra):
        """
        DADO 3 órdenes aprobadas en enero para Proveedor Test SA
        CUANDO se consulta compras_por_proveedor en enero
        ENTONCES num_ordenes=3 y total_comprado=1000.00
        """
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert len(resultado) == 1
        fila = resultado[0]
        assert fila["num_ordenes"] == 3
        assert fila["total_comprado"] == Decimal("1000.00")

    def test_ordenes_canceladas_excluidas(self, db_connection, seed_ordenes_compra):
        """OC-CAN (cancelada) no debe sumarse al total del proveedor."""
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["total_comprado"] == Decimal("1000.00")

    def test_filtro_fecha_excluye_febrero(self, db_connection, seed_ordenes_compra):
        """OC-004 de febrero no debe aparecer al filtrar solo enero."""
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["num_ordenes"] == 3

    def test_periodo_sin_compras_retorna_vacio(self, db_connection, seed_ordenes_compra):
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2024-01-01", "2024-01-31")
        )
        assert resultado == []

    def test_nombre_proveedor_correcto(self, db_connection, seed_ordenes_compra):
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["proveedor"] == "Proveedor Test SA"


class TestOrdenesCompraEstado:

    def test_conteo_por_estado(self, db_connection, seed_ordenes_compra):
        """Verificar directamente el conteo de órdenes por estado en enero."""
        sql = """
            SELECT estado, COUNT(*) AS total
            FROM ordenes_compra
            WHERE deleted_at IS NULL
              AND fecha_emision BETWEEN %s AND %s
              AND id_sucursal = %s
            GROUP BY estado
        """
        resultado = ejecutar_query(
            db_connection, sql,
            ("2025-01-01", "2025-01-31", 901)
        )
        por_estado = {r["estado"]: r["total"] for r in resultado}
        assert por_estado.get("aprobada") == 3
        assert por_estado.get("cancelada") == 1

    def test_orden_soft_deleted_no_aparece(self, db_connection, seed_ordenes_compra):
        """Una orden con deleted_at no debe aparecer en consultas."""
        cur = db_connection.cursor()
        cur.execute("UPDATE ordenes_compra SET deleted_at = NOW() WHERE id = 901")
        cur.close()
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["num_ordenes"] == 2
