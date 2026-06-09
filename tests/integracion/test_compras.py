"""
Tests de integración E2E para compras.

Flujo de cada test:
  1. seed_ordenes_compra inserta en d_ordenes_compra (DB desnormalizada) → COMMIT → ejecuta ETL
  2. El test hace asserts sobre r_ordenes_compra (DB resumen, dst_conn)

Diferencia con reportes_desn/test_compras.py: verifica que la cadena completa
desnormalizada → ETL → resumen produzca los resultados correctos.
"""
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query, QUERIES_RESUMEN_DIR
from db.importar_resumen import importar_tabla


class TestComprasPorProveedorIntegracion:

    def test_total_enero_tres_ordenes(self, dst_conn, seed_ordenes_compra):
        """
        DADO 3 órdenes aprobadas en enero en d_ordenes_compra
        CUANDO el ETL importa r_ordenes_compra
        ENTONCES num_ordenes=3 y total_comprado=1000.00 en la DB resumen
        """
        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        assert len(resultado) == 1
        fila = resultado[0]
        assert fila["num_ordenes"] == 3
        assert fila["total_comprado"] == Decimal("1000.00")

    def test_canceladas_excluidas_por_query(self, dst_conn, seed_ordenes_compra):
        """OC-CAN existe en r_ordenes_compra (el ETL la importa) pero la query la excluye."""
        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        assert resultado[0]["total_comprado"] == Decimal("1000.00")

    def test_filtro_fecha_excluye_febrero(self, dst_conn, seed_ordenes_compra):
        """OC-I04 de febrero no aparece al filtrar solo enero."""
        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        assert resultado[0]["num_ordenes"] == 3

    def test_periodo_sin_compras_retorna_vacio(self, dst_conn, seed_ordenes_compra):
        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2024-01-01", "2024-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        assert resultado == []

    def test_nombre_proveedor_correcto(self, dst_conn, seed_ordenes_compra):
        """El nombre del proveedor proviene del campo embebido en d_ordenes_compra."""
        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        assert resultado[0]["proveedor"] == "Proveedor Test SA"


class TestOrdenesCompraEstadoIntegracion:

    def test_etl_importa_canceladas(self, dst_conn, seed_ordenes_compra):
        """
        El ETL importa todas las órdenes no eliminadas de d_ordenes_compra (sin filtrar por estado).
        La query de reporte es la responsable de excluir canceladas.
        """
        sql = """
            SELECT estado, COUNT(*) AS total
            FROM r_ordenes_compra
            WHERE deleted_at IS NULL
              AND fecha_emision BETWEEN %s AND %s
            GROUP BY estado
        """
        resultado = ejecutar_query(
            dst_conn, sql,
            ("2025-01-01", "2025-01-31")
        )
        por_estado = {r["estado"]: r["total"] for r in resultado}
        assert por_estado.get("aprobada") == 3
        assert por_estado.get("cancelada") == 1

    def test_etl_excluye_soft_deleted(self, src_conn, dst_conn, seed_ordenes_compra):
        """
        El ETL extrae con WHERE deleted_at IS NULL en d_ordenes_compra.
        Al soft-delete una orden y re-ejecutar el ETL, desaparece de r_ordenes_compra.
        """
        cur = src_conn.cursor()
        cur.execute("UPDATE d_ordenes_compra SET deleted_at = NOW() WHERE id = 801")
        src_conn.commit()
        cur.close()

        # Re-ejecutar ETL: TRUNCATE + INSERT sin la orden soft-deleted
        importar_tabla(src_conn, dst_conn, "r_ordenes_compra", batch_size=500)

        resultado = ejecutar_reporte(
            dst_conn, "compras_por_proveedor.sql",
            ("2025-01-01", "2025-01-31"),
            queries_dir=QUERIES_RESUMEN_DIR,
        )
        # OC-802 y OC-803 aprobadas en enero; OC-801 excluida por soft-delete
        assert resultado[0]["num_ordenes"] == 2
