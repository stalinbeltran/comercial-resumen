"""
Tests unitarios de etl/transformadores.py.
Sin base de datos — funciones puras pandas → pandas.
"""
import pytest
import pandas as pd
from datetime import date, datetime

import etl.transformadores as tr

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# transformar_inventario
# ---------------------------------------------------------------------------

class TestTransformarInventario:

    def _df(self, **kwargs):
        row = dict(
            id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
            id_presentacion=1, presentacion="Unidad",
            id_bodega=1, bodega="Bodega Principal",
            stock_actual=50.0, stock_minimo=10.0, stock_maximo=100.0,
            deleted_at=None, extra_col="ignorar",
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_solo_columnas_destino(self):
        out = tr.transformar_inventario(self._df())
        assert "extra_col" not in out.columns

    def test_columnas_obligatorias_presentes(self):
        out = tr.transformar_inventario(self._df())
        for col in ["id_producto", "id_bodega", "stock_actual", "deleted_at"]:
            assert col in out.columns

    def test_preserva_valores(self):
        out = tr.transformar_inventario(self._df(stock_actual=99.5))
        assert float(out["stock_actual"].iloc[0]) == 99.5


# ---------------------------------------------------------------------------
# transformar_movimientos
# ---------------------------------------------------------------------------

class TestTransformarMovimientos:

    def _df(self, **kwargs):
        row = dict(
            id_movimiento_orig=1,
            id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
            id_bodega=1, bodega="Bodega Principal",
            fecha="2026-01-15 08:00:00", tipo_movimiento="entrada",
            cantidad=10.0, cantidad_anterior=0.0, cantidad_posterior=10.0,
            costo_unitario=800.00, tipo_referencia=None,
            id_referencia=None, observacion=None, deleted_at=None,
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_fecha_convertida_a_datetime(self):
        out = tr.transformar_movimientos(self._df())
        assert pd.api.types.is_datetime64_any_dtype(out["fecha"])

    def test_fecha_valor_correcto(self):
        out = tr.transformar_movimientos(self._df(fecha="2026-03-20 10:30:00"))
        assert out["fecha"].iloc[0] == pd.Timestamp("2026-03-20 10:30:00")

    def test_solo_columnas_destino(self):
        out = tr.transformar_movimientos(self._df())
        assert "extra" not in out.columns


# ---------------------------------------------------------------------------
# transformar_facturas
# ---------------------------------------------------------------------------

class TestTransformarFacturas:

    def _df(self, **kwargs):
        row = dict(
            id_factura_orig=1, numero_factura="F-001",
            fecha_emision="2026-01-15", fecha_vencimiento="2026-02-14",
            id_sucursal=1, sucursal="Sucursal Centro",
            id_cliente=1, cliente="Cliente ABC",
            subtotal=1000.00, descuento=0.00, impuesto=120.00,
            total=1120.00, saldo=0.00,
            estado="pagada", deleted_at=None,
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_fecha_emision_convertida_a_date(self):
        out = tr.transformar_facturas(self._df())
        assert isinstance(out["fecha_emision"].iloc[0], date)

    def test_fecha_vencimiento_convertida_a_date(self):
        out = tr.transformar_facturas(self._df())
        assert isinstance(out["fecha_vencimiento"].iloc[0], date)

    def test_fecha_vencimiento_nula_queda_none(self):
        out = tr.transformar_facturas(self._df(fecha_vencimiento=None))
        assert out["fecha_vencimiento"].iloc[0] is None or pd.isna(out["fecha_vencimiento"].iloc[0])

    def test_estado_category_se_convierte_a_str(self):
        df = self._df()
        df["estado"] = df["estado"].astype("category")
        out = tr.transformar_facturas(df)
        assert out["estado"].dtype == object

    def test_solo_columnas_destino(self):
        df = self._df()
        df["columna_extra"] = "x"
        out = tr.transformar_facturas(df)
        assert "columna_extra" not in out.columns

    def test_preserva_valores_monetarios(self):
        out = tr.transformar_facturas(self._df(total=1500.50, saldo=500.00))
        assert float(out["total"].iloc[0]) == 1500.50
        assert float(out["saldo"].iloc[0]) == 500.00


# ---------------------------------------------------------------------------
# transformar_facturas_detalle
# ---------------------------------------------------------------------------

class TestTransformarFacturasDetalle:

    def _df(self, **kwargs):
        row = dict(
            id_detalle_orig=1, id_factura=1, numero_factura="F-001",
            fecha_emision="2026-01-15", id_sucursal=1, estado_factura="pagada",
            id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
            id_categoria=1, categoria="Electrónica",
            cantidad=2.0, subtotal=2000.00, costo_unitario=800.00,
            deleted_at=None,
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_fecha_emision_convertida_a_date(self):
        out = tr.transformar_facturas_detalle(self._df())
        assert isinstance(out["fecha_emision"].iloc[0], date)

    def test_estado_factura_category_se_convierte_a_str(self):
        df = self._df()
        df["estado_factura"] = df["estado_factura"].astype("category")
        out = tr.transformar_facturas_detalle(df)
        assert out["estado_factura"].dtype == object

    def test_id_categoria_nulo_se_preserva(self):
        out = tr.transformar_facturas_detalle(self._df(id_categoria=None, categoria=None))
        assert out["id_categoria"].iloc[0] is None or pd.isna(out["id_categoria"].iloc[0])


# ---------------------------------------------------------------------------
# transformar_ordenes_compra
# ---------------------------------------------------------------------------

class TestTransformarOrdenesCompra:

    def _df(self, **kwargs):
        row = dict(
            id_orden_orig=1, id_proveedor=1, proveedor="Proveedor MNO",
            fecha_emision="2026-01-10", estado="recibida",
            total=5000.00, deleted_at=None,
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_fecha_emision_convertida_a_date(self):
        out = tr.transformar_ordenes_compra(self._df())
        assert isinstance(out["fecha_emision"].iloc[0], date)

    def test_estado_category_se_convierte_a_str(self):
        df = self._df()
        df["estado"] = df["estado"].astype("category")
        out = tr.transformar_ordenes_compra(df)
        assert out["estado"].dtype == object

    def test_solo_columnas_destino(self):
        df = self._df()
        df["extra"] = "x"
        out = tr.transformar_ordenes_compra(df)
        assert "extra" not in out.columns
