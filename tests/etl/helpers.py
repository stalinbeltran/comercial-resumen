"""
Helpers reutilizables para los tests del ETL.

Contiene:
- Funciones de inserción en tablas d_* (fuente) y r_* (destino)
- Funciones de consulta (contar, leer_tabla, ultimo_run)
- Datos base reutilizables (FACTURA_BASE, DETALLE_BASE, etc.)

Reglas:
- IDs fijos y bajos (1, 2, 3) — nunca auto-generados
- Fechas fijas absolutas — nunca date.today()
- La lógica de datos vive aquí; los tests solo orquestan
"""
import decimal
from datetime import date, datetime

import pandas as pd
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Datos base (mínimos válidos) — reutilizar y sobrescribir según necesidad
# ---------------------------------------------------------------------------

INVENTARIO_BASE = dict(
    id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
    id_presentacion=1, presentacion="Unidad",
    id_bodega=1, bodega="Bodega Principal",
    stock_actual=50, stock_minimo=10, stock_maximo=100,
)

MOVIMIENTO_BASE = dict(
    id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
    id_bodega=1, bodega="Bodega Principal",
    tipo_movimiento="entrada",
    cantidad=10, cantidad_anterior=0, cantidad_posterior=10,
    costo_unitario=800.00,
)

FACTURA_BASE = dict(
    numero_factura="F-001",
    fecha_emision="2026-01-15", fecha_vencimiento="2026-02-14",
    id_sucursal=1, sucursal="Sucursal Centro",
    id_cliente=1, cliente="Cliente ABC",
    subtotal=1000.00, descuento=0.00, impuesto=120.00,
    total=1120.00, saldo=0.00,
    estado="pagada",
)

DETALLE_BASE = dict(
    id_factura=1, numero_factura="F-001",
    fecha_emision="2026-01-15", id_sucursal=1, estado_factura="pagada",
    id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
    id_categoria=1, categoria="Electrónica",
    cantidad=1, subtotal=1000.00, costo_unitario=800.00,
)

ORDEN_BASE = dict(
    id_proveedor=1, proveedor="Proveedor MNO",
    fecha_emision="2026-01-10",
    estado="recibida", total=5000.00,
)


# ---------------------------------------------------------------------------
# Inserción en tablas fuente (d_*)
# ---------------------------------------------------------------------------

def insertar_d_inventario(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO d_inventario "
        "(id_producto, codigo_producto, nombre_producto, "
        " id_presentacion, presentacion, id_bodega, bodega, "
        " stock_actual, stock_minimo, stock_maximo) "
        "VALUES (:id_producto, :codigo_producto, :nombre_producto, "
        "        :id_presentacion, :presentacion, :id_bodega, :bodega, "
        "        :stock_actual, :stock_minimo, :stock_maximo)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def insertar_d_movimientos(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO d_movimientos_inventario "
        "(id_producto, codigo_producto, nombre_producto, "
        " id_bodega, bodega, tipo_movimiento, "
        " cantidad, cantidad_anterior, cantidad_posterior, costo_unitario) "
        "VALUES (:id_producto, :codigo_producto, :nombre_producto, "
        "        :id_bodega, :bodega, :tipo_movimiento, "
        "        :cantidad, :cantidad_anterior, :cantidad_posterior, :costo_unitario)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def insertar_d_facturas(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO d_facturas "
        "(id, numero_factura, fecha_emision, fecha_vencimiento, "
        " id_sucursal, sucursal, id_cliente, cliente, "
        " subtotal, descuento, impuesto, total, saldo, estado) "
        "VALUES (:id, :numero_factura, :fecha_emision, :fecha_vencimiento, "
        "        :id_sucursal, :sucursal, :id_cliente, :cliente, "
        "        :subtotal, :descuento, :impuesto, :total, :saldo, :estado)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def insertar_d_detalle(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO d_facturas_detalle "
        "(id, id_factura, numero_factura, fecha_emision, id_sucursal, estado_factura, "
        " id_producto, codigo_producto, nombre_producto, id_categoria, categoria, "
        " cantidad, subtotal, costo_unitario) "
        "VALUES (:id, :id_factura, :numero_factura, :fecha_emision, :id_sucursal, :estado_factura, "
        "        :id_producto, :codigo_producto, :nombre_producto, :id_categoria, :categoria, "
        "        :cantidad, :subtotal, :costo_unitario)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def insertar_d_ordenes(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO d_ordenes_compra "
        "(id, id_proveedor, proveedor, fecha_emision, estado, total) "
        "VALUES (:id, :id_proveedor, :proveedor, :fecha_emision, :estado, :total)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def forzar_updated_at(engine, tabla: str, id_val: int, ts: str) -> None:
    """Sobreescribe updated_at en un registro concreto para controlar watermarks."""
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {tabla} SET updated_at = :ts WHERE id = :id"),
            {"ts": ts, "id": id_val},
        )


def insertar_r_facturas(engine, filas: list[dict]) -> None:
    """Inserta directamente en r_facturas (para tests de UPSERT que necesitan estado previo)."""
    sql = text(
        "INSERT INTO r_facturas "
        "(id_factura_orig, numero_factura, fecha_emision, fecha_vencimiento, "
        " id_sucursal, sucursal, id_cliente, cliente, "
        " subtotal, descuento, impuesto, total, saldo, estado) "
        "VALUES (:id_factura_orig, :numero_factura, :fecha_emision, :fecha_vencimiento, "
        "        :id_sucursal, :sucursal, :id_cliente, :cliente, "
        "        :subtotal, :descuento, :impuesto, :total, :saldo, :estado)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


def insertar_r_ordenes(engine, filas: list[dict]) -> None:
    sql = text(
        "INSERT INTO r_ordenes_compra "
        "(id_orden_orig, id_proveedor, proveedor, fecha_emision, estado, total) "
        "VALUES (:id_orden_orig, :id_proveedor, :proveedor, :fecha_emision, :estado, :total)"
    )
    with engine.begin() as conn:
        conn.execute(sql, filas)


# ---------------------------------------------------------------------------
# Consultas helpers
# ---------------------------------------------------------------------------

def contar(engine, tabla: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()


def leer_tabla(engine, tabla: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {tabla}"), conn)


def leer_campo(engine, tabla: str, campo: str, where: str, params: dict):
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT {campo} FROM {tabla} WHERE {where}"), params
        ).scalar()


def ultimo_run(engine, tabla: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM etl_runs "
                "WHERE tabla = :t ORDER BY id DESC LIMIT 1"
            ),
            {"t": tabla},
        ).mappings().fetchone()
    return dict(row) if row else {}
