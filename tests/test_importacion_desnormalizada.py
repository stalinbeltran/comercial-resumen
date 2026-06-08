"""
Verifica que db/importar_desnormalizada.py haya cargado datos correctos
en comercial_desn_db a partir de comercial_db.

Estos tests NO usan rollback ni seeds: leen el estado real de ambas BDs
después de haber ejecutado el script de importación.

Ejecución:
    1. python db/importar_desnormalizada.py
    2. pytest tests/test_importacion_desnormalizada.py -v
"""
import os
import pytest
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Fixtures de conexión (sin rollback — solo lectura)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def src():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME"),
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def dst():
    conn = mysql.connector.connect(
        host=os.getenv("DB_DESN_HOST", "localhost"),
        port=int(os.getenv("DB_DESN_PORT", 3306)),
        user=os.getenv("DB_DESN_USER", "root"),
        password=os.getenv("DB_DESN_PASSWORD", ""),
        database=os.getenv("DB_DESN_NAME"),
    )
    yield conn
    conn.close()


def _count(conn, tabla: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE deleted_at IS NULL")
    (n,) = cur.fetchone()
    cur.close()
    return n


def _scalar(conn, sql: str) -> object:
    cur = conn.cursor()
    cur.execute(sql)
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# d_inventario
# ---------------------------------------------------------------------------

class TestDInventario:

    def test_conteo_igual_a_origen(self, src, dst):
        """d_inventario debe tener una fila por cada fila activa de inventario."""
        n_src = _count(src, "inventario")
        n_dst = _count(dst, "d_inventario")
        assert n_dst == n_src, (
            f"d_inventario tiene {n_dst} filas pero inventario origen tiene {n_src}"
        )

    def test_no_hay_nulos_en_campos_obligatorios(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM d_inventario
            WHERE codigo_producto IS NULL
               OR nombre_producto IS NULL
               OR bodega IS NULL
               OR presentacion IS NULL
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} filas con campos obligatorios nulos en d_inventario"

    def test_stock_actual_coincide_con_origen(self, src, dst):
        """La suma de stock_actual debe ser igual entre origen y destino."""
        suma_src = _scalar(src, "SELECT COALESCE(SUM(cantidad), 0) FROM inventario WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(stock_actual), 0) FROM d_inventario WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma stock_actual: origen={suma_src} destino={suma_dst}"
        )


# ---------------------------------------------------------------------------
# d_movimientos_inventario
# ---------------------------------------------------------------------------

class TestDMovimientosInventario:

    def test_conteo_igual_a_origen(self, src, dst):
        n_src = _count(src, "movimientos_inventario")
        n_dst = _count(dst, "d_movimientos_inventario")
        assert n_dst == n_src, (
            f"d_movimientos_inventario tiene {n_dst} pero origen tiene {n_src}"
        )

    def test_id_movimiento_orig_unico(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_movimiento_orig
                FROM d_movimientos_inventario
                WHERE deleted_at IS NULL
                GROUP BY id_movimiento_orig
                HAVING COUNT(*) > 1
            ) dup
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} valores duplicados en d_movimientos_inventario.id_movimiento_orig"

    def test_no_hay_nulos_en_campos_obligatorios(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM d_movimientos_inventario
            WHERE codigo_producto IS NULL
               OR nombre_producto IS NULL
               OR bodega IS NULL
               OR tipo_movimiento IS NULL
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} filas con campos obligatorios nulos en d_movimientos_inventario"

    def test_suma_cantidad_coincide_con_origen(self, src, dst):
        suma_src = _scalar(src, "SELECT COALESCE(SUM(cantidad), 0) FROM movimientos_inventario WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(cantidad), 0) FROM d_movimientos_inventario WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma cantidad: origen={suma_src} destino={suma_dst}"
        )


# ---------------------------------------------------------------------------
# d_facturas
# ---------------------------------------------------------------------------

class TestDFacturas:

    def test_conteo_igual_a_origen(self, src, dst):
        n_src = _count(src, "facturas")
        n_dst = _count(dst, "d_facturas")
        assert n_dst == n_src, (
            f"d_facturas tiene {n_dst} filas pero facturas origen tiene {n_src}"
        )

    def test_id_factura_orig_unico(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_factura_orig
                FROM d_facturas
                WHERE deleted_at IS NULL
                GROUP BY id_factura_orig
                HAVING COUNT(*) > 1
            ) dup
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} valores duplicados en d_facturas.id_factura_orig"

    def test_total_ventas_coincide_con_origen(self, src, dst):
        suma_src = _scalar(src, "SELECT COALESCE(SUM(total), 0) FROM facturas WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(total), 0) FROM d_facturas WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma total facturas: origen={suma_src} destino={suma_dst}"
        )

    def test_saldo_ventas_coincide_con_origen(self, src, dst):
        suma_src = _scalar(src, "SELECT COALESCE(SUM(saldo), 0) FROM facturas WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(saldo), 0) FROM d_facturas WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma saldo facturas: origen={suma_src} destino={suma_dst}"
        )

    def test_no_hay_nulos_en_campos_obligatorios(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM d_facturas
            WHERE numero_factura IS NULL
               OR sucursal IS NULL
               OR cliente IS NULL
               OR estado IS NULL
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} filas con campos obligatorios nulos en d_facturas"


# ---------------------------------------------------------------------------
# d_facturas_detalle
# ---------------------------------------------------------------------------

class TestDFacturasDetalle:

    def test_conteo_igual_a_origen(self, src, dst):
        n_src = _count(src, "facturas_detalle")
        n_dst = _count(dst, "d_facturas_detalle")
        assert n_dst == n_src, (
            f"d_facturas_detalle tiene {n_dst} filas pero facturas_detalle origen tiene {n_src}"
        )

    def test_id_detalle_orig_unico(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_detalle_orig
                FROM d_facturas_detalle
                WHERE deleted_at IS NULL
                GROUP BY id_detalle_orig
                HAVING COUNT(*) > 1
            ) dup
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} valores duplicados en d_facturas_detalle.id_detalle_orig"

    def test_subtotal_coincide_con_origen(self, src, dst):
        suma_src = _scalar(src, "SELECT COALESCE(SUM(subtotal), 0) FROM facturas_detalle WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(subtotal), 0) FROM d_facturas_detalle WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma subtotal detalle: origen={suma_src} destino={suma_dst}"
        )

    def test_no_hay_nulos_en_campos_obligatorios(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM d_facturas_detalle
            WHERE codigo_producto IS NULL
               OR nombre_producto IS NULL
               OR numero_factura IS NULL
               OR estado_factura IS NULL
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} filas con campos obligatorios nulos en d_facturas_detalle"


# ---------------------------------------------------------------------------
# d_ordenes_compra
# ---------------------------------------------------------------------------

class TestDOrdenesCompra:

    def test_conteo_igual_a_origen(self, src, dst):
        n_src = _count(src, "ordenes_compra")
        n_dst = _count(dst, "d_ordenes_compra")
        assert n_dst == n_src, (
            f"d_ordenes_compra tiene {n_dst} filas pero ordenes_compra origen tiene {n_src}"
        )

    def test_id_orden_orig_unico(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT id_orden_orig
                FROM d_ordenes_compra
                WHERE deleted_at IS NULL
                GROUP BY id_orden_orig
                HAVING COUNT(*) > 1
            ) dup
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} valores duplicados en d_ordenes_compra.id_orden_orig"

    def test_total_compras_coincide_con_origen(self, src, dst):
        suma_src = _scalar(src, "SELECT COALESCE(SUM(total), 0) FROM ordenes_compra WHERE deleted_at IS NULL")
        suma_dst = _scalar(dst, "SELECT COALESCE(SUM(total), 0) FROM d_ordenes_compra WHERE deleted_at IS NULL")
        assert float(suma_src) == float(suma_dst), (
            f"Suma total compras: origen={suma_src} destino={suma_dst}"
        )

    def test_no_hay_nulos_en_campos_obligatorios(self, dst):
        cur = dst.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM d_ordenes_compra
            WHERE proveedor IS NULL
               OR estado IS NULL
        """)
        (n,) = cur.fetchone()
        cur.close()
        assert n == 0, f"{n} filas con campos obligatorios nulos en d_ordenes_compra"
