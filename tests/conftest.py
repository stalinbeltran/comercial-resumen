"""
Fixtures globales de pytest para la base de datos comercial_db_test.
Requiere variables de entorno en .env o definidas en el entorno:
  DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME (default: comercial_db_test)
"""
import os
import pytest
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "comercial_db_test"),
}


@pytest.fixture(scope="session")
def db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def rollback(db_connection):
    """Envuelve cada test en una transacción que se revierte al terminar."""
    db_connection.start_transaction()
    yield
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Fixtures de entidades base (reutilizables entre módulos)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def seed_base(db_connection):
    """
    Inserta el árbol mínimo de entidades maestras necesario para los tests:
    empresa → sucursal → bodega → unidad_medida → marca → categoria → producto → presentacion.
    Retorna un dict con los IDs fijos para usar en assertions.
    """
    cur = db_connection.cursor()

    cur.execute("""
        INSERT INTO empresas (id, razon_social, ruc_rif, moneda)
        VALUES (901, 'Empresa Test SA', '1790000001001', 'USD')
    """)
    cur.execute("""
        INSERT INTO sucursales (id, id_empresa, nombre, codigo, estado)
        VALUES (901, 901, 'Sucursal Principal Test', 'SUC-T01', 1)
    """)
    cur.execute("""
        INSERT INTO bodegas (id, id_sucursal, nombre, codigo, estado)
        VALUES (901, 901, 'Bodega Principal Test', 'BOD-T01', 1)
    """)
    cur.execute("""
        INSERT INTO unidades_medida (id, nombre, abreviatura)
        VALUES (901, 'Unidad Test', 'UNT')
    """)
    cur.execute("""
        INSERT INTO marcas (id, nombre)
        VALUES (901, 'Marca Test')
    """)
    cur.execute("""
        INSERT INTO categorias (id, nombre)
        VALUES (901, 'Categoria Test')
    """)
    cur.execute("""
        INSERT INTO productos (id, id_categoria, id_marca, id_unidad_medida,
                               codigo, nombre, aplica_impuesto, porcentaje_impuesto, estado)
        VALUES (901, 901, 901, 901, 'PROD-T01', 'Producto Test Uno', 1, 12.00, 1)
    """)
    cur.execute("""
        INSERT INTO productos (id, id_categoria, id_marca, id_unidad_medida,
                               codigo, nombre, aplica_impuesto, porcentaje_impuesto, estado)
        VALUES (902, 901, 901, 901, 'PROD-T02', 'Producto Test Dos', 1, 12.00, 1)
    """)
    cur.execute("""
        INSERT INTO productos_presentaciones (id, id_producto, nombre, factor_conversion, estado)
        VALUES (901, 901, 'Unidad', 1.0000, 1)
    """)
    cur.execute("""
        INSERT INTO productos_presentaciones (id, id_producto, nombre, factor_conversion, estado)
        VALUES (902, 902, 'Unidad', 1.0000, 1)
    """)

    cur.close()
    return {
        "id_empresa":      901,
        "id_sucursal":     901,
        "id_bodega":       901,
        "id_unidad":       901,
        "id_marca":        901,
        "id_categoria":    901,
        "id_producto_1":   901,
        "id_producto_2":   902,
        "id_presentacion_1": 901,
        "id_presentacion_2": 902,
    }


@pytest.fixture(scope="function")
def seed_terceros(db_connection):
    """Inserta tipo de identificacion, un cliente y un proveedor."""
    cur = db_connection.cursor()
    cur.execute("""
        INSERT INTO tipos_identificacion (id, nombre, codigo)
        VALUES (901, 'RUC Test', 'RUC')
    """)
    cur.execute("""
        INSERT INTO terceros (id, id_tipo_identificacion, numero_identificacion,
                              razon_social, estado)
        VALUES (901, 901, '1790000001001', 'Cliente Test SA', 1)
    """)
    cur.execute("""
        INSERT INTO terceros_tipos (id, id_tercero, tipo)
        VALUES (901, 901, 'cliente')
    """)
    cur.execute("""
        INSERT INTO terceros (id, id_tipo_identificacion, numero_identificacion,
                              razon_social, estado)
        VALUES (902, 901, '1790000002001', 'Proveedor Test SA', 1)
    """)
    cur.execute("""
        INSERT INTO terceros_tipos (id, id_tercero, tipo)
        VALUES (902, 902, 'proveedor')
    """)
    cur.close()
    return {"id_cliente": 901, "id_proveedor": 902, "id_tipo_ident": 901}


@pytest.fixture(scope="function")
def seed_formas_pago(db_connection):
    cur = db_connection.cursor()
    cur.execute("""
        INSERT INTO formas_pago (id, nombre, tipo, requiere_referencia, estado)
        VALUES (901, 'Efectivo Test', 'efectivo', 0, 1)
    """)
    cur.execute("""
        INSERT INTO formas_pago (id, nombre, tipo, requiere_referencia, estado)
        VALUES (902, 'Transferencia Test', 'transferencia', 1, 1)
    """)
    cur.close()
    return {"id_efectivo": 901, "id_transferencia": 902}
