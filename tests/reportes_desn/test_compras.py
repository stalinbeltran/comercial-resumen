"""
Tests del módulo de Compras sobre la BD desnormalizada.

Misma lógica de negocio que tests/reportes/test_compras.py pero siembra
directamente en d_ordenes_compra — sin la cadena de FKs de la BD normalizada.

Si algún test falla aquí y pasa en tests/reportes/test_compras.py, el error
está en la query SQL desnormalizada o en el proceso de importación ETL.
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixture de seed
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_ordenes_compra(db_connection):
    """
    Mismos datos de negocio que el test normalizado, insertados en d_ordenes_compra:
      OC-001  aprobada  enero     500.00
      OC-002  aprobada  enero     300.00
      OC-003  aprobada  enero     200.00
      OC-004  aprobada  febrero   999.00
      OC-CAN  cancelada enero     100.00
    """
    cur = db_connection.cursor()
    cur.executemany("""
        INSERT INTO d_ordenes_compra
            (id, id_orden_orig, id_proveedor, proveedor, fecha_emision, estado, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, [
        (901, 901, 902, 'Proveedor Test SA', '2025-01-05', 'aprobada',  500.00),
        (902, 902, 902, 'Proveedor Test SA', '2025-01-12', 'aprobada',  300.00),
        (903, 903, 902, 'Proveedor Test SA', '2025-01-20', 'aprobada',  200.00),
        (904, 904, 902, 'Proveedor Test SA', '2025-02-03', 'aprobada',  999.00),
        (905, 905, 902, 'Proveedor Test SA', '2025-01-08', 'cancelada', 100.00),
    ])
    cur.close()


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
            FROM d_ordenes_compra
            WHERE deleted_at IS NULL
              AND fecha_emision BETWEEN %s AND %s
            GROUP BY estado
        """
        resultado = ejecutar_query(
            db_connection, sql,
            ("2025-01-01", "2025-01-31")
        )
        por_estado = {r["estado"]: r["total"] for r in resultado}
        assert por_estado.get("aprobada") == 3
        assert por_estado.get("cancelada") == 1

    def test_orden_soft_deleted_no_aparece(self, db_connection, seed_ordenes_compra):
        """Una orden con deleted_at no debe aparecer en consultas."""
        cur = db_connection.cursor()
        cur.execute("UPDATE d_ordenes_compra SET deleted_at = NOW() WHERE id = 901")
        cur.close()
        resultado = ejecutar_reporte(
            db_connection, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["num_ordenes"] == 2
