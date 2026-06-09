"""
Transformaciones pandas por tabla.

Cada función recibe un chunk de datos del extractor y retorna el DataFrame
listo para ser cargado en la tabla r_* de destino.
Las transformaciones son ligeras: limpieza de tipos, columnas derivadas
y selección de columnas destino. La lógica de negocio pesada (agregaciones)
vive en la capa de extracción (SQL) o en las tablas de reportes.
"""
import pandas as pd


# ---------------------------------------------------------------------------
# Columnas destino por tabla — garantizan orden y presencia exacta
# ---------------------------------------------------------------------------
_COLS_INVENTARIO = [
    "id_producto", "codigo_producto", "nombre_producto",
    "id_presentacion", "presentacion",
    "id_bodega", "bodega",
    "stock_actual", "stock_minimo", "stock_maximo",
    "deleted_at",
]

_COLS_MOVIMIENTOS = [
    "id_movimiento_orig",
    "id_producto", "codigo_producto", "nombre_producto",
    "id_bodega", "bodega",
    "fecha", "tipo_movimiento",
    "cantidad", "cantidad_anterior", "cantidad_posterior",
    "costo_unitario", "tipo_referencia", "id_referencia", "observacion",
    "deleted_at",
]

_COLS_FACTURAS = [
    "id_factura_orig", "numero_factura",
    "fecha_emision", "fecha_vencimiento",
    "id_sucursal", "sucursal",
    "id_cliente", "cliente",
    "subtotal", "descuento", "impuesto", "total", "saldo",
    "estado", "deleted_at",
]

_COLS_DETALLE = [
    "id_detalle_orig", "id_factura", "numero_factura",
    "fecha_emision", "id_sucursal", "estado_factura",
    "id_producto", "codigo_producto", "nombre_producto",
    "id_categoria", "categoria",
    "cantidad", "subtotal", "costo_unitario",
    "deleted_at",
]

_COLS_ORDENES = [
    "id_orden_orig", "id_proveedor", "proveedor",
    "fecha_emision", "estado", "total",
    "deleted_at",
]


def _seleccionar(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Retorna solo las columnas destino en el orden correcto."""
    presentes = [c for c in cols if c in df.columns]
    return df[presentes].copy()


# ---------------------------------------------------------------------------
# Transformadores públicos
# ---------------------------------------------------------------------------

def transformar_inventario(df: pd.DataFrame) -> pd.DataFrame:
    return _seleccionar(df, _COLS_INVENTARIO)


def transformar_movimientos(df: pd.DataFrame) -> pd.DataFrame:
    df = _seleccionar(df, _COLS_MOVIMIENTOS)
    # Asegura que `fecha` es datetime para una inserción limpia
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def transformar_facturas(df: pd.DataFrame) -> pd.DataFrame:
    df = _seleccionar(df, _COLS_FACTURAS)
    if "fecha_emision" in df.columns:
        df["fecha_emision"] = pd.to_datetime(df["fecha_emision"]).dt.date
    if "fecha_vencimiento" in df.columns:
        df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"], errors="coerce").dt.date
    # Categorías son válidas en pandas pero MySQL recibe el string subyacente
    for col in ("estado",):
        if col in df.columns and hasattr(df[col], "cat"):
            df[col] = df[col].astype(str)
    return df


def transformar_facturas_detalle(df: pd.DataFrame) -> pd.DataFrame:
    df = _seleccionar(df, _COLS_DETALLE)
    if "fecha_emision" in df.columns:
        df["fecha_emision"] = pd.to_datetime(df["fecha_emision"]).dt.date
    for col in ("estado_factura",):
        if col in df.columns and hasattr(df[col], "cat"):
            df[col] = df[col].astype(str)
    return df


def transformar_ordenes_compra(df: pd.DataFrame) -> pd.DataFrame:
    df = _seleccionar(df, _COLS_ORDENES)
    if "fecha_emision" in df.columns:
        df["fecha_emision"] = pd.to_datetime(df["fecha_emision"]).dt.date
    for col in ("estado",):
        if col in df.columns and hasattr(df[col], "cat"):
            df[col] = df[col].astype(str)
    return df
