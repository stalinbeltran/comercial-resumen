"""
Tests de integración de etl/cargadores.py.
Verifican las tres estrategias de escritura contra la BD destino de test.
"""
import pytest
import pandas as pd
from sqlalchemy import text

import etl.cargadores as carg
from tests.etl.helpers import (
    contar, leer_campo, insertar_r_facturas, insertar_r_ordenes,
    FACTURA_BASE, ORDEN_BASE,
)

pytestmark = pytest.mark.integration

# Columnas que el UPSERT actualiza en r_facturas
_COLS_UPDATE_FACTURAS = [
    "numero_factura", "fecha_emision", "fecha_vencimiento",
    "id_sucursal", "sucursal", "id_cliente", "cliente",
    "subtotal", "descuento", "impuesto", "total", "saldo",
    "estado", "deleted_at",
]

_COLS_UPDATE_ORDENES = [
    "id_proveedor", "proveedor", "fecha_emision",
    "estado", "total", "deleted_at",
]


def _df_factura(**kwargs):
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


def _df_orden(**kwargs):
    row = dict(
        id_orden_orig=1, id_proveedor=1, proveedor="Proveedor MNO",
        fecha_emision="2026-01-10", estado="recibida",
        total=5000.00, deleted_at=None,
    )
    row.update(kwargs)
    return pd.DataFrame([row])


def _df_inventario(**kwargs):
    row = dict(
        id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
        id_presentacion=1, presentacion="Unidad",
        id_bodega=1, bodega="Bodega Principal",
        stock_actual=50.0, stock_minimo=10.0, stock_maximo=100.0,
        deleted_at=None,
    )
    row.update(kwargs)
    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# truncar_y_cargar
# ---------------------------------------------------------------------------

class TestTruncarYCargar:

    def test_inserta_filas(self, engine_dst, patch_engines):
        df = pd.concat([_df_inventario(), _df_inventario(id_producto=2)])
        filas = carg.truncar_y_cargar(df, "r_inventario")
        assert filas == 2
        assert contar(engine_dst, "r_inventario") == 2

    def test_trunca_antes_de_insertar(self, engine_dst, patch_engines):
        df1 = _df_inventario()
        carg.truncar_y_cargar(df1, "r_inventario")

        df2 = _df_inventario(id_producto=99, stock_actual=999)
        carg.truncar_y_cargar(df2, "r_inventario")

        assert contar(engine_dst, "r_inventario") == 1

    def test_dataframe_vacio_retorna_cero(self, engine_dst, patch_engines):
        filas = carg.truncar_y_cargar(pd.DataFrame(), "r_inventario")
        assert filas == 0
        assert contar(engine_dst, "r_inventario") == 0

    def test_dry_run_no_escribe(self, engine_dst, patch_engines):
        df = _df_inventario()
        filas = carg.truncar_y_cargar(df, "r_inventario", dry_run=True)
        assert filas == 1
        assert contar(engine_dst, "r_inventario") == 0


# ---------------------------------------------------------------------------
# cargar_incremental
# ---------------------------------------------------------------------------

class TestCargarIncremental:

    def _df_movimiento(self, id_mov=1, **kwargs):
        row = dict(
            id_movimiento_orig=id_mov,
            id_producto=1, codigo_producto="P001", nombre_producto="Laptop",
            id_bodega=1, bodega="Bodega Principal",
            fecha=pd.Timestamp("2026-01-15 08:00:00"),
            tipo_movimiento="entrada",
            cantidad=10.0, cantidad_anterior=0.0, cantidad_posterior=10.0,
            costo_unitario=800.00, tipo_referencia=None,
            id_referencia=None, observacion=None, deleted_at=None,
        )
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_inserta_filas(self, engine_dst, patch_engines):
        df = self._df_movimiento()
        filas = carg.cargar_incremental(df, "r_movimientos_inventario")
        assert filas == 1
        assert contar(engine_dst, "r_movimientos_inventario") == 1

    def test_segunda_carga_acumula_sin_truncar(self, engine_dst, patch_engines):
        carg.cargar_incremental(self._df_movimiento(id_mov=1), "r_movimientos_inventario")
        carg.cargar_incremental(self._df_movimiento(id_mov=2), "r_movimientos_inventario")
        assert contar(engine_dst, "r_movimientos_inventario") == 2

    def test_dry_run_no_escribe(self, engine_dst, patch_engines):
        filas = carg.cargar_incremental(
            self._df_movimiento(), "r_movimientos_inventario", dry_run=True
        )
        assert filas == 1
        assert contar(engine_dst, "r_movimientos_inventario") == 0


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

class TestUpsert:

    def test_inserta_registro_nuevo(self, engine_dst, patch_engines):
        filas = carg.upsert(_df_factura(), "r_facturas", _COLS_UPDATE_FACTURAS)
        assert filas == 1
        assert contar(engine_dst, "r_facturas") == 1

    def test_actualiza_campo_mutable_en_registro_existente(self, engine_dst, patch_engines):
        """
        DADO   un registro en r_facturas con saldo=500
        CUANDO se hace upsert con saldo=0 para el mismo id_factura_orig
        ENTONCES el saldo en destino queda en 0
        """
        insertar_r_facturas(engine_dst, [{**FACTURA_BASE, "id_factura_orig": 1, "saldo": 500.00}])
        carg.upsert(_df_factura(saldo=0.00), "r_facturas", _COLS_UPDATE_FACTURAS)
        saldo = leer_campo(engine_dst, "r_facturas", "saldo",
                           "id_factura_orig = :id", {"id": 1})
        assert float(saldo) == 0.00

    def test_actualiza_estado_en_registro_existente(self, engine_dst, patch_engines):
        insertar_r_facturas(engine_dst, [{**FACTURA_BASE, "id_factura_orig": 1, "estado": "pendiente"}])
        carg.upsert(_df_factura(estado="pagada"), "r_facturas", _COLS_UPDATE_FACTURAS)
        estado = leer_campo(engine_dst, "r_facturas", "estado",
                            "id_factura_orig = :id", {"id": 1})
        assert estado == "pagada"

    def test_idempotente_registro_sin_cambios(self, engine_dst, patch_engines):
        carg.upsert(_df_factura(), "r_facturas", _COLS_UPDATE_FACTURAS)
        carg.upsert(_df_factura(), "r_facturas", _COLS_UPDATE_FACTURAS)
        assert contar(engine_dst, "r_facturas") == 1

    def test_propaga_deleted_at(self, engine_dst, patch_engines):
        insertar_r_facturas(engine_dst, [{**FACTURA_BASE, "id_factura_orig": 1}])
        carg.upsert(
            _df_factura(deleted_at=pd.Timestamp("2026-06-01")),
            "r_facturas", _COLS_UPDATE_FACTURAS,
        )
        deleted = leer_campo(engine_dst, "r_facturas", "deleted_at",
                              "id_factura_orig = :id", {"id": 1})
        assert deleted is not None

    def test_dry_run_no_escribe(self, engine_dst, patch_engines):
        filas = carg.upsert(_df_factura(), "r_facturas", _COLS_UPDATE_FACTURAS, dry_run=True)
        assert filas == 1
        assert contar(engine_dst, "r_facturas") == 0
