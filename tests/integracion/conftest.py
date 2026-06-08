"""
Fixtures para tests de integración E2E.
Flujo: seed en DB normalizada → COMMIT → ETL → asserts en DB desnormalizada.
IDs en rango 801-809: no colisionan con fixtures de reportes/ (rango 900+).
"""
import os
import pytest
import mysql.connector
from dotenv import load_dotenv

from db.importar_desnormalizada import importar_tabla

load_dotenv()

_SRC_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "comercial_db"),
}

_DST_CONFIG = {
    "host":     os.getenv("DB_DESN_HOST", "localhost"),
    "port":     int(os.getenv("DB_DESN_PORT", 3306)),
    "user":     os.getenv("DB_DESN_USER", "root"),
    "password": os.getenv("DB_DESN_PASSWORD", ""),
    "database": os.getenv("DB_DESN_NAME", "comercial_desn_db"),
}


@pytest.fixture(scope="session")
def src_conn():
    """Conexión a DB normalizada (autocommit=False; los fixtures hacen commit explícito)."""
    conn = mysql.connector.connect(**_SRC_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def dst_conn():
    """Conexión a DB desnormalizada para leer resultados post-ETL."""
    conn = mysql.connector.connect(**_DST_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture
def seed_ordenes_compra(src_conn, dst_conn):
    """
    Siembra el árbol FK mínimo + órdenes de compra en DB normalizada,
    hace COMMIT, ejecuta el ETL y deja d_ordenes_compra lista para asserts.

    Datos (IDs 801-805):
      OC-I01  aprobada  enero     500.00
      OC-I02  aprobada  enero     300.00
      OC-I03  aprobada  enero     200.00
      OC-I04  aprobada  febrero   999.00
      OC-CAN  cancelada enero     100.00
    """
    cur = src_conn.cursor()

    cur.execute("""
        INSERT INTO empresas (id, razon_social, ruc_rif, moneda)
        VALUES (801, 'Empresa Integ SA', '1790000801001', 'USD')
    """)
    cur.execute("""
        INSERT INTO sucursales (id, id_empresa, nombre, codigo, estado)
        VALUES (801, 801, 'Sucursal Integ', 'SUC-I01', 1)
    """)
    cur.execute("""
        INSERT INTO bodegas (id, id_sucursal, nombre, codigo, estado)
        VALUES (801, 801, 'Bodega Integ', 'BOD-I01', 1)
    """)
    cur.execute("""
        INSERT INTO tipos_identificacion (id, nombre, codigo)
        VALUES (801, 'RUC Integ', 'RUC')
    """)
    cur.execute("""
        INSERT INTO terceros (id, id_tipo_identificacion, numero_identificacion, razon_social, estado)
        VALUES (801, 801, '1790000801001', 'Cliente Integ SA', 1)
    """)
    cur.execute("""
        INSERT INTO terceros_tipos (id, id_tercero, tipo)
        VALUES (801, 801, 'cliente')
    """)
    cur.execute("""
        INSERT INTO terceros (id, id_tipo_identificacion, numero_identificacion, razon_social, estado)
        VALUES (802, 801, '1790000802001', 'Proveedor Test SA', 1)
    """)
    cur.execute("""
        INSERT INTO terceros_tipos (id, id_tercero, tipo)
        VALUES (802, 802, 'proveedor')
    """)
    cur.executemany("""
        INSERT INTO ordenes_compra
            (id, id_sucursal, id_proveedor, id_bodega_destino, numero, fecha_emision,
             estado, subtotal, descuento, impuesto, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 802, 801, 'OC-I01', '2025-01-05', 'aprobada',  446.43, 0, 53.57, 500.00),
        (802, 801, 802, 801, 'OC-I02', '2025-01-12', 'aprobada',  267.86, 0, 32.14, 300.00),
        (803, 801, 802, 801, 'OC-I03', '2025-01-20', 'aprobada',  178.57, 0, 21.43, 200.00),
        (804, 801, 802, 801, 'OC-I04', '2025-02-03', 'aprobada',  891.96, 0, 107.04, 999.00),
        (805, 801, 802, 801, 'OC-CAN', '2025-01-08', 'cancelada',  89.29, 0, 10.71, 100.00),
    ])
    cur.close()

    # COMMIT requerido: el ETL abre su propio cursor y solo ve datos committed
    src_conn.commit()

    # ETL: extrae de normalizada e inserta en desnormalizada (TRUNCATE + INSERT + COMMIT)
    importar_tabla(src_conn, dst_conn, "d_ordenes_compra", batch_size=500)

    yield  # test corre aquí con d_ordenes_compra poblada

    # --- Teardown normalizada (orden inverso de FK) ---
    cur = src_conn.cursor()
    cur.execute("DELETE FROM ordenes_compra WHERE id IN (801,802,803,804,805)")
    cur.execute("DELETE FROM terceros_tipos WHERE id IN (801,802)")
    cur.execute("DELETE FROM terceros WHERE id IN (801,802)")
    cur.execute("DELETE FROM tipos_identificacion WHERE id = 801")
    cur.execute("DELETE FROM bodegas WHERE id = 801")
    cur.execute("DELETE FROM sucursales WHERE id = 801")
    cur.execute("DELETE FROM empresas WHERE id = 801")
    src_conn.commit()
    cur.close()

    # --- Teardown desnormalizada ---
    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE d_ordenes_compra")
    dst_conn.commit()
    dst_cur.close()


# ---------------------------------------------------------------------------
# Fixtures compartidos para ventas, inventario, tesorería y gerenciales
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_base_integ(src_conn):
    """
    Árbol completo de entidades maestras para tests de ventas/inventario/tesorería/gerenciales.
    IDs 801-802.  El teardown corre DESPUÉS de los fixtures dependientes (LIFO).
    """
    cur = src_conn.cursor()
    cur.execute("INSERT INTO empresas (id, razon_social, ruc_rif, moneda) VALUES (801, 'Empresa Integ SA', '1790000801001', 'USD')")
    cur.execute("INSERT INTO sucursales (id, id_empresa, nombre, codigo, estado) VALUES (801, 801, 'Sucursal Integ', 'SUC-I01', 1)")
    cur.execute("INSERT INTO bodegas (id, id_sucursal, nombre, codigo, estado) VALUES (801, 801, 'Bodega Integ', 'BOD-I01', 1)")
    cur.execute("INSERT INTO unidades_medida (id, nombre, abreviatura) VALUES (801, 'Unidad Integ', 'UNI')")
    cur.execute("INSERT INTO marcas (id, nombre) VALUES (801, 'Marca Integ')")
    cur.execute("INSERT INTO categorias (id, nombre) VALUES (801, 'Categoria Integ')")
    cur.execute("INSERT INTO productos (id, id_categoria, id_marca, id_unidad_medida, codigo, nombre, aplica_impuesto, porcentaje_impuesto, estado) VALUES (801, 801, 801, 801, 'PROD-I01', 'Producto Integ Uno', 1, 12.00, 1)")
    cur.execute("INSERT INTO productos (id, id_categoria, id_marca, id_unidad_medida, codigo, nombre, aplica_impuesto, porcentaje_impuesto, estado) VALUES (802, 801, 801, 801, 'PROD-I02', 'Producto Integ Dos', 1, 12.00, 1)")
    cur.execute("INSERT INTO productos_presentaciones (id, id_producto, nombre, factor_conversion, estado) VALUES (801, 801, 'Unidad', 1.0000, 1)")
    cur.execute("INSERT INTO productos_presentaciones (id, id_producto, nombre, factor_conversion, estado) VALUES (802, 802, 'Unidad', 1.0000, 1)")
    cur.execute("INSERT INTO tipos_identificacion (id, nombre, codigo) VALUES (801, 'RUC Integ', 'RUC')")
    cur.execute("INSERT INTO terceros (id, id_tipo_identificacion, numero_identificacion, razon_social, estado) VALUES (801, 801, '1790000801001', 'Cliente Integ SA', 1)")
    cur.execute("INSERT INTO terceros_tipos (id, id_tercero, tipo) VALUES (801, 801, 'cliente')")
    cur.close()
    src_conn.commit()

    yield {
        "id_empresa": 801, "id_sucursal": 801, "id_bodega": 801,
        "id_producto_1": 801, "id_producto_2": 802,
        "id_presentacion_1": 801, "id_presentacion_2": 802,
        "id_cliente": 801,
    }

    cur = src_conn.cursor()
    cur.execute("DELETE FROM terceros_tipos WHERE id = 801")
    cur.execute("DELETE FROM terceros WHERE id = 801")
    cur.execute("DELETE FROM tipos_identificacion WHERE id = 801")
    cur.execute("DELETE FROM productos_presentaciones WHERE id IN (801,802)")
    cur.execute("DELETE FROM productos WHERE id IN (801,802)")
    cur.execute("DELETE FROM bodegas WHERE id = 801")
    cur.execute("DELETE FROM sucursales WHERE id = 801")
    cur.execute("DELETE FROM categorias WHERE id = 801")
    cur.execute("DELETE FROM marcas WHERE id = 801")
    cur.execute("DELETE FROM unidades_medida WHERE id = 801")
    cur.execute("DELETE FROM empresas WHERE id = 801")
    src_conn.commit()
    cur.close()


@pytest.fixture
def seed_facturas(src_conn, dst_conn, seed_base_integ):
    """
    3 activas en enero + 1 en febrero + 1 anulada.  ETL → d_facturas.

      F-I01  activa   enero    100.00
      F-I02  activa   enero    200.00
      F-I03  activa   enero    300.00
      F-I04  activa   febrero  999.00
      F-ANU  anulada  enero    500.00
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, subtotal, descuento, impuesto, total, saldo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'F-I01', '2025-01-10', '2025-02-10', 'activa',   89.29, 0,  10.71, 100.00, 100.00),
        (802, 801, 801, 'F-I02', '2025-01-15', '2025-02-15', 'activa',  178.57, 0,  21.43, 200.00, 200.00),
        (803, 801, 801, 'F-I03', '2025-01-20', '2025-02-20', 'activa',  267.86, 0,  32.14, 300.00, 300.00),
        (804, 801, 801, 'F-I04', '2025-02-05', '2025-03-05', 'activa',  891.96, 0, 107.04, 999.00, 999.00),
        (805, 801, 801, 'F-ANU', '2025-01-25', '2025-02-25', 'anulada', 446.43, 0,  53.57, 500.00, 500.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_facturas", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM facturas WHERE id IN (801,802,803,804,805)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE d_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_facturas_con_detalle(src_conn, dst_conn, seed_facturas):
    """
    Agrega detalle a F-I01/F-I02 (prod 801) y F-I03 (prod 802).  ETL → d_facturas_detalle.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO facturas_detalle
            (id, id_factura, id_producto, id_presentacion, id_bodega,
             cantidad, precio_unitario, descuento, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 801, 801,  5.0000, 20.00, 0, 100.00, 10.00),
        (802, 802, 801, 801, 801, 10.0000, 20.00, 0, 200.00, 10.00),
        (803, 803, 802, 802, 801, 15.0000, 20.00, 0, 300.00, 10.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_facturas_detalle", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM facturas_detalle WHERE id IN (801,802,803)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE d_facturas_detalle")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_inventario(src_conn, dst_conn, seed_base_integ):
    """
    Stock: prod 801 = 50 und (normal), prod 802 = 3 und (bajo mínimo 10).  ETL → d_inventario.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO inventario
            (id, id_producto, id_presentacion, id_bodega,
             cantidad, cantidad_minima, cantidad_maxima)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 801, 50.0000, 10.0000, 200.0000),
        (802, 802, 802, 801,  3.0000, 10.0000, 100.0000),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_inventario", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM inventario WHERE id IN (801,802)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE d_inventario")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_kardex(src_conn, dst_conn, seed_inventario):
    """
    3 movimientos del prod 801 en bodega 801: +30 → +20 → -15. Saldo final = 35.
    ETL → d_movimientos_inventario.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO movimientos_inventario
            (id, id_producto, id_presentacion, id_bodega,
             tipo_movimiento, cantidad, cantidad_anterior, cantidad_posterior, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 801, 'entrada', 30,  0, 30, 5.00),
        (802, 801, 801, 801, 'entrada', 20, 30, 50, 5.00),
        (803, 801, 801, 801, 'salida',  15, 50, 35, 5.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_movimientos_inventario", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM movimientos_inventario WHERE id IN (801,802,803)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("TRUNCATE TABLE d_movimientos_inventario")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_cxc(src_conn, dst_conn, seed_base_integ):
    """
    6 facturas con distintos vencimientos al corte 2025-03-01.  ETL → d_facturas.

      F-VIG  activa   vence 2025-03-15  saldo=500  → vigente
      F-030  activa   vence 2025-02-10  saldo=200  → 1-30
      F-060  activa   vence 2025-01-20  saldo=300  → 31-60
      F-090  vencida  vence 2024-12-30  saldo=400  → 61-90
      F-MAS  vencida  vence 2024-11-01  saldo=100  → +90
      F-PAG  pagada   saldo=0            → excluida
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, total, saldo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'F-VIG', '2025-01-10', '2025-03-15', 'activa',  500.00, 500.00),
        (802, 801, 801, 'F-030', '2025-01-10', '2025-02-10', 'activa',  200.00, 200.00),
        (803, 801, 801, 'F-060', '2025-01-10', '2025-01-20', 'activa',  300.00, 300.00),
        (804, 801, 801, 'F-090', '2024-12-01', '2024-12-30', 'vencida', 400.00, 400.00),
        (805, 801, 801, 'F-MAS', '2024-10-01', '2024-11-01', 'vencida', 100.00, 100.00),
        (806, 801, 801, 'F-PAG', '2025-01-01', '2025-02-01', 'pagada',  999.00,   0.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_facturas", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM facturas WHERE id IN (801,802,803,804,805,806)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE d_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()


@pytest.fixture
def seed_ventas_gerencial(src_conn, dst_conn, seed_base_integ):
    """
    Enero: Prod1=100 und ($2000) + Prod2=30 und ($600).
    Diciembre: Prod1=50 und ($1000).
    ETL → d_facturas y d_facturas_detalle.
    """
    cur = src_conn.cursor()
    cur.executemany("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, subtotal, descuento, impuesto, total, saldo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 'FG-I01', '2025-01-10', '2025-02-10', 'activa', 2321.43, 0, 278.57, 2600.00, 2600.00),
        (802, 801, 801, 'FG-I02', '2024-12-15', '2025-01-15', 'activa',  892.86, 0, 107.14, 1000.00, 1000.00),
    ])
    cur.executemany("""
        INSERT INTO facturas_detalle
            (id, id_factura, id_producto, id_presentacion, id_bodega,
             cantidad, precio_unitario, descuento, subtotal, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        (801, 801, 801, 801, 801, 100.0000, 20.00, 0, 2000.00, 8.00),
        (802, 801, 802, 802, 801,  30.0000, 20.00, 0,  600.00, 8.00),
        (803, 802, 801, 801, 801,  50.0000, 20.00, 0, 1000.00, 8.00),
    ])
    cur.close()
    src_conn.commit()
    importar_tabla(src_conn, dst_conn, "d_facturas", batch_size=500)
    importar_tabla(src_conn, dst_conn, "d_facturas_detalle", batch_size=500)

    yield

    cur = src_conn.cursor()
    cur.execute("DELETE FROM facturas_detalle WHERE id IN (801,802,803)")
    cur.execute("DELETE FROM facturas WHERE id IN (801,802)")
    src_conn.commit()
    cur.close()

    dst_cur = dst_conn.cursor()
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute("TRUNCATE TABLE d_facturas_detalle")
    dst_cur.execute("TRUNCATE TABLE d_facturas")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    dst_conn.commit()
    dst_cur.close()
