"""
Tests de integración E2E para inventario.

Flujo: inventario/movimientos en DB normalizada → ETL (d_inventario, d_movimientos_inventario)
       → asserts en desnormalizada.
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query
from db.importar_desnormalizada import importar_tabla


class TestStockPorBodegaIntegracion:

    def test_retorna_filas_para_bodega_con_stock(self, dst_conn, seed_inventario):
        """DADO stock para 2 productos en bodega 801 CUANDO ETL importa ENTONCES retorna 2 filas."""
        resultado = ejecutar_reporte(dst_conn, "inventario.sql", (801,))
        assert len(resultado) == 2

    def test_cantidades_exactas(self, dst_conn, seed_inventario):
        """Las cantidades en d_inventario deben coincidir con lo insertado en normalizada."""
        resultado = ejecutar_reporte(dst_conn, "inventario.sql", (801,))
        stocks = {r["codigo_producto"]: r["stock_actual"] for r in resultado}
        assert stocks["PROD-I01"] == Decimal("50.0000")
        assert stocks["PROD-I02"] == Decimal("3.0000")

    def test_bodega_inexistente_retorna_lista_vacia(self, dst_conn, seed_inventario):
        """Bodega sin registros en d_inventario retorna lista vacía."""
        resultado = ejecutar_reporte(dst_conn, "inventario.sql", (9999,))
        assert resultado == []

    def test_etl_excluye_productos_soft_deleted(self, src_conn, dst_conn, seed_inventario):
        """El ETL JOIN con productos usa AND p.deleted_at IS NULL; re-ejecutar excluye el producto."""
        cur = src_conn.cursor()
        cur.execute("UPDATE productos SET deleted_at = NOW() WHERE id = 801")
        src_conn.commit()
        cur.close()

        importar_tabla(src_conn, dst_conn, "d_inventario", batch_size=500)

        resultado = ejecutar_reporte(dst_conn, "inventario.sql", (801,))
        codigos = [r["codigo_producto"] for r in resultado]
        assert "PROD-I01" not in codigos
        assert len(resultado) == 1


class TestProductosBajoMinimoIntegracion:

    def test_detecta_producto_bajo_minimo(self, dst_conn, seed_inventario):
        """
        DADO prod 802 con stock=3 y mínimo=10
        CUANDO el ETL importa d_inventario
        ENTONCES aparece solo prod 802 en productos_bajo_minimo
        """
        resultado = ejecutar_reporte(dst_conn, "productos_bajo_minimo.sql", (801,))
        assert len(resultado) == 1
        assert resultado[0]["codigo_producto"] == "PROD-I02"

    def test_no_incluye_productos_con_stock_suficiente(self, dst_conn, seed_inventario):
        """Prod 801 con stock=50 > mínimo=10 no debe aparecer."""
        resultado = ejecutar_reporte(dst_conn, "productos_bajo_minimo.sql", (801,))
        codigos = [r["codigo_producto"] for r in resultado]
        assert "PROD-I01" not in codigos

    def test_bodega_inexistente_retorna_vacio(self, dst_conn, seed_inventario):
        resultado = ejecutar_reporte(dst_conn, "productos_bajo_minimo.sql", (9999,))
        assert resultado == []

    def test_stock_igual_a_minimo_no_aparece(self, src_conn, dst_conn, seed_inventario):
        """Stock exactamente igual al mínimo no se considera bajo mínimo; re-ejecutar ETL lo refleja."""
        cur = src_conn.cursor()
        cur.execute("UPDATE inventario SET cantidad = 10.0000 WHERE id = 802")
        src_conn.commit()
        cur.close()

        importar_tabla(src_conn, dst_conn, "d_inventario", batch_size=500)

        resultado = ejecutar_reporte(dst_conn, "productos_bajo_minimo.sql", (801,))
        assert resultado == []


class TestKardexIntegracion:

    def test_numero_de_movimientos(self, dst_conn, seed_kardex):
        """
        DADO 3 movimientos del prod 801 en bodega 801 en DB normalizada
        CUANDO el ETL importa d_movimientos_inventario
        ENTONCES retorna exactamente 3 filas en kardex
        """
        resultado = ejecutar_reporte(
            dst_conn, "kardex.sql",
            (801, 801, "2020-01-01", "2099-12-31")
        )
        assert len(resultado) == 3

    def test_saldo_final_cuadra(self, dst_conn, seed_kardex):
        """El movimiento de salida (-15) debe dejar saldo posterior = 35."""
        resultado = ejecutar_reporte(
            dst_conn, "kardex.sql",
            (801, 801, "2020-01-01", "2099-12-31")
        )
        salida = next(r for r in resultado if r["tipo_movimiento"] == "salida")
        assert salida["cantidad_posterior"] == Decimal("35.0000")

    def test_filtro_fecha_excluye_movimientos_fuera_de_rango(self, dst_conn, seed_kardex):
        """Un rango de fechas anterior a la inserción no retorna ningún movimiento."""
        resultado = ejecutar_reporte(
            dst_conn, "kardex.sql",
            (801, 801, "2000-01-01", "2000-01-31")
        )
        assert resultado == []

    def test_secuencia_de_saldos_coherente(self, dst_conn, seed_kardex):
        """cantidad_posterior = cantidad_anterior ± cantidad según tipo de movimiento."""
        resultado = ejecutar_reporte(
            dst_conn, "kardex.sql",
            (801, 801, "2020-01-01", "2099-12-31")
        )
        for r in resultado:
            if r["tipo_movimiento"] == "entrada":
                esperado = r["cantidad_anterior"] + r["cantidad"]
            else:
                esperado = r["cantidad_anterior"] - r["cantidad"]
            assert r["cantidad_posterior"] == pytest.approx(float(esperado), abs=0.0001)
