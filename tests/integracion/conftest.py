"""
Fixtures para tests de integración E2E.
Flujo: seed directo en DB desnormalizada (d_*) → COMMIT → ETL → asserts en DB resumen (r_*).
IDs en rango 801-809: no colisionan con fixtures de reportes/ (rango 900+).
"""
import os
import pytest
import mysql.connector
from dotenv import load_dotenv

from db.importar_resumen import importar_tabla

load_dotenv()

_SRC_CONFIG = {
    "host":     os.getenv("DB_DESN_HOST", "localhost"),
    "port":     int(os.getenv("DB_DESN_PORT", 3306)),
    "user":     os.getenv("DB_DESN_USER", "root"),
    "password": os.getenv("DB_DESN_PASSWORD", ""),
    "database": os.getenv("DB_DESN_NAME", "comercial_desn_db"),
}

_DST_CONFIG = {
    "host":     os.getenv("DB_RESUMEN_HOST", "localhost"),
    "port":     int(os.getenv("DB_RESUMEN_PORT", 3306)),
    "user":     os.getenv("DB_RESUMEN_USER", "root"),
    "password": os.getenv("DB_RESUMEN_PASSWORD", ""),
    "database": os.getenv("DB_RESUMEN_NAME", "comercial_resumen_db"),
}


@pytest.fixture(scope="session")
def src_conn():
    """Conexión a DB desnormalizada (autocommit=False; los fixtures hacen commit explícito)."""
    conn = mysql.connector.connect(**_SRC_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def dst_conn():
    """Conexión a DB resumen para leer resultados post-ETL."""
    conn = mysql.connector.connect(**_DST_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture
def seed_ordenes_compra(src_conn, dst_conn):
    """
    Siembra órdenes de compra directamente en d_ordenes_compra,
    hace COMMIT, ejecuta el ETL y deja r_ordenes_compra lista para asserts.

    Datos (IDs 801-805):
      OC-I01  aprobada  enero     500.00
      OC-I02  aprobada  enero     300.00
      OC-I03  aprobada  enero     200.00
      OC-I04  aprobada  febrero   999.00
      OC-CAN  cancelada enero     100.00
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_ordenes_compra
            (id, id_orden_orig, id_proveedor, proveedor, fecha_emision, estado, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 802, 'Proveedor Test SA', '2025-01-05', 'aprobada',  500.00),
        (802, 802, 802, 'Proveedor Test SA', '2025-01-12', 'aprobada',  300.00),
        (803, 803, 802, 'Proveedor Test SA', '2025-01-20', 'aprobada',  200.00),
        (804, 804, 802, 'Proveedor Test SA', '2025-02-03', 'aprobada',  999.00),
        (805, 805, 802, 'Proveedor Test SA', '2025-01-08', 'cancelada', 100.00),
    ])
    cur.close()

    # COMMIT requerido: el ETL abre su propio cursor y solo ve datos committed
    src_conn.commit()

    # ETL: extrae de desnormalizada e inserta en resumen (TRUNCATE + INSERT + COMMIT)
    importar_tabla(src_conn, dst_conn, "r_ordenes_compra", batch_size=500)

    yield  # test corre aquí con r_ordenes_compra poblada

    # --- Teardown desnormalizada ---
    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_ordenes_compra WHERE id IN (801,802,803,804,805)")
    src_conn.commit()
    cur.close()

    # --- Teardown resumen ---
    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE r_ordenes_compra")
    dst_conn.commit()
    dst_cur.close()


# ---------------------------------------------------------------------------
# Fixtures compartidos para ventas, inventario, tesorería y gerenciales
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_facturas(src_conn, dst_conn):
    """
    3 activas en enero + 1 en febrero + 1 anulada.  ETL → r_facturas.

      F-I01  activa   enero    100.00
      F-I02  activa   enero    200.00
      F-I03  activa   enero    300.00
      F-I04  activa   febrero  999.00
      F-ANU  anulada  enero    500.00
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_facturas
            (id, id_factura_orig, numero_factura, fecha_emision, fecha_vencimiento,
             id_sucursal, sucursal, id_cliente, cliente,
             subtotal, descuento, impuesto, total, saldo, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 'F-I01', '2025-01-10', '2025-02-10', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',   89.29, 0,  10.71, 100.00, 100.00, 'activa'),
        (802, 802, 'F-I02', '2025-01-15', '2025-02-15', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  178.57, 0,  21.43, 200.00, 200.00, 'activa'),
        (803, 803, 'F-I03', '2025-01-20', '2025-02-20', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  267.86, 0,  32.14, 300.00, 300.00, 'activa'),
        (804, 804, 'F-I04', '2025-02-05', '2025-03-05', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  891.96, 0, 107.04, 999.00, 999.00, 'activa'),
        (805, 805, 'F-ANU', '2025-01-25', '2025-02-25', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  446.43, 0,  53.57, 500.00, 500.00, 'anulada'),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_facturas", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_facturas WHERE id IN (801,802,803,804,805)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE r_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_facturas_con_detalle(src_conn, dst_conn, seed_facturas):
    """
    Agrega detalle a F-I01/F-I02 (prod 801) y F-I03 (prod 802).  ETL → r_facturas_detalle.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_facturas_detalle
            (id, id_detalle_orig, id_factura, numero_factura, fecha_emision,
             id_sucursal, estado_factura,
             id_producto, codigo_producto, nombre_producto, id_categoria, categoria,
             cantidad, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'F-I01', '2025-01-10', 801, 'activa', 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Categoria Integ',  5.0000, 100.00, 10.00),
        (802, 802, 802, 'F-I02', '2025-01-15', 801, 'activa', 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Categoria Integ', 10.0000, 200.00, 10.00),
        (803, 803, 803, 'F-I03', '2025-01-20', 801, 'activa', 802, 'PROD-I02', 'Producto Integ Dos', 801, 'Categoria Integ', 15.0000, 300.00, 10.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_facturas_detalle", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_facturas_detalle WHERE id IN (801,802,803)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE r_facturas_detalle")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_inventario(src_conn, dst_conn):
    """
    Stock: prod 801 = 50 und (normal), prod 802 = 3 und (bajo mínimo 10).  ETL → r_inventario.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_inventario
            (id, id_producto, codigo_producto, nombre_producto,
             id_presentacion, presentacion, id_bodega, bodega,
             stock_actual, stock_minimo, stock_maximo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Unidad', 801, 'Bodega Integ', 50.0000, 10.0000, 200.0000),
        (802, 802, 'PROD-I02', 'Producto Integ Dos', 802, 'Unidad', 801, 'Bodega Integ',  3.0000, 10.0000, 100.0000),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_inventario", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_inventario WHERE id IN (801,802)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE r_inventario")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_kardex(src_conn, dst_conn):
    """
    3 movimientos del prod 801 en bodega 801: +30 → +20 → -15. Saldo final = 35.
    ETL → r_movimientos_inventario.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_movimientos_inventario
            (id, id_movimiento_orig,
             id_producto, codigo_producto, nombre_producto,
             id_bodega, bodega, fecha, tipo_movimiento,
             cantidad, cantidad_anterior, cantidad_posterior, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Bodega Integ', '2025-01-01 08:00:00', 'entrada', 30,  0, 30, 5.00),
        (802, 802, 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Bodega Integ', '2025-01-01 09:00:00', 'entrada', 20, 30, 50, 5.00),
        (803, 803, 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Bodega Integ', '2025-01-01 10:00:00', 'salida',  15, 50, 35, 5.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_movimientos_inventario", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_movimientos_inventario WHERE id IN (801,802,803)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE r_movimientos_inventario")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_cxc(src_conn, dst_conn):
    """
    6 facturas con distintos vencimientos al corte 2025-03-01.  ETL → r_facturas.

      F-VIG  activa   vence 2025-03-15  saldo=500  → vigente
      F-030  activa   vence 2025-02-10  saldo=200  → 1-30
      F-060  activa   vence 2025-01-20  saldo=300  → 31-60
      F-090  vencida  vence 2024-12-30  saldo=400  → 61-90
      F-MAS  vencida  vence 2024-11-01  saldo=100  → +90
      F-PAG  pagada   saldo=0            → excluida
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_facturas
            (id, id_factura_orig, numero_factura, fecha_emision, fecha_vencimiento,
             id_sucursal, sucursal, id_cliente, cliente, total, saldo, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 'F-VIG', '2025-01-10', '2025-03-15', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  500.00, 500.00, 'activa'),
        (802, 802, 'F-030', '2025-01-10', '2025-02-10', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  200.00, 200.00, 'activa'),
        (803, 803, 'F-060', '2025-01-10', '2025-01-20', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  300.00, 300.00, 'activa'),
        (804, 804, 'F-090', '2024-12-01', '2024-12-30', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  400.00, 400.00, 'vencida'),
        (805, 805, 'F-MAS', '2024-10-01', '2024-11-01', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  100.00, 100.00, 'vencida'),
        (806, 806, 'F-PAG', '2025-01-01', '2025-02-01', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  999.00,   0.00, 'pagada'),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_facturas", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_facturas WHERE id IN (801,802,803,804,805,806)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE r_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_ventas_gerencial(src_conn, dst_conn):
    """
    Enero: Prod1=100 und ($2000) + Prod2=30 und ($600).
    Diciembre: Prod1=50 und ($1000).
    ETL → r_facturas y r_facturas_detalle.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO d_facturas
            (id, id_factura_orig, numero_factura, fecha_emision, fecha_vencimiento,
             id_sucursal, sucursal, id_cliente, cliente,
             subtotal, descuento, impuesto, total, saldo, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 'FG-I01', '2025-01-10', '2025-02-10', 801, 'Sucursal Integ', 801, 'Cliente Integ SA', 2321.43, 0, 278.57, 2600.00, 2600.00, 'activa'),
        (802, 802, 'FG-I02', '2024-12-15', '2025-01-15', 801, 'Sucursal Integ', 801, 'Cliente Integ SA',  892.86, 0, 107.14, 1000.00, 1000.00, 'activa'),
    ])
    cur.executemany("""
        INSERT INTO d_facturas_detalle
            (id, id_detalle_orig, id_factura, numero_factura, fecha_emision,
             id_sucursal, estado_factura,
             id_producto, codigo_producto, nombre_producto, id_categoria, categoria,
             cantidad, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'FG-I01', '2025-01-10', 801, 'activa', 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Categoria Integ', 100.0000, 2000.00, 8.00),
        (802, 802, 801, 'FG-I01', '2025-01-10', 801, 'activa', 802, 'PROD-I02', 'Producto Integ Dos', 801, 'Categoria Integ',  30.0000,  600.00, 8.00),
        (803, 803, 802, 'FG-I02', '2024-12-15', 801, 'activa', 801, 'PROD-I01', 'Producto Integ Uno', 801, 'Categoria Integ',  50.0000, 1000.00, 8.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "r_facturas", batch_size=500)
    importar_tabla(src_conn, dst_conn, "r_facturas_detalle", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM d_facturas_detalle WHERE id IN (801,802,803)")
    cur.execute("DELETE FROM d_facturas WHERE id IN (801,802)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE r_facturas_detalle")
    dst_cur.execute("TRUNCATE TABLE r_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()
