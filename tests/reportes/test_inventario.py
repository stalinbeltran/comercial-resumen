"""
Tests del módulo de Inventario.

Cubre:
  - Stock actual por bodega
  - Productos bajo mínimo
  - Kardex: entradas y salidas cuadran con saldo
  - Caso borde: bodega sin registros
"""
import pytest
from decimal import Decimal
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixtures de inventario
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_inventario(db_connection, seed_base):
    """Stock inicial: Producto 1 = 50 und, Producto 2 = 3 und (bajo mínimo de 10)."""
    cur = db_connection.cursor()
    cur.execute("""
        INSERT INTO inventario (id, id_producto, id_presentacion, id_bodega,
                                cantidad, cantidad_minima, cantidad_maxima)
        VALUES (901, 901, 901, 901, 50.0000, 10.0000, 200.0000)
    """)
    cur.execute("""
        INSERT INTO inventario (id, id_producto, id_presentacion, id_bodega,
                                cantidad, cantidad_minima, cantidad_maxima)
        VALUES (902, 902, 902, 901, 3.0000, 10.0000, 100.0000)
    """)
    cur.close()
    return seed_base


@pytest.fixture
def seed_kardex(db_connection, seed_inventario):
    """
    Kardex del Producto 1 en Bodega 901:
      entrada  +30  → saldo 30
      entrada  +20  → saldo 50
      salida   -15  → saldo 35
    Saldo esperado final: 35
    """
    cur = db_connection.cursor()
    movimientos = [
        (901, 901, 901, 901, 'entrada', 30, 0,  30,  5.00),
        (902, 901, 901, 901, 'entrada', 20, 30, 50,  5.00),
        (903, 901, 901, 901, 'salida',  15, 50, 35,  5.00),
    ]
    cur.executemany("""
        INSERT INTO movimientos_inventario
            (id, id_producto, id_presentacion, id_bodega,
             tipo_movimiento, cantidad, cantidad_anterior, cantidad_posterior, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, movimientos)
    cur.close()
    return seed_inventario


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStockPorBodega:

    def test_retorna_filas_para_bodega_con_stock(self, db_connection, seed_inventario):
        """DADO stock en bodega 901 CUANDO se consulta stock_por_bodega ENTONCES retorna 2 filas."""
        resultado = ejecutar_reporte(db_connection, "inventario.sql", (901,))
        assert len(resultado) == 2

    def test_cantidades_exactas(self, db_connection, seed_inventario):
        """Las cantidades deben coincidir exactamente con lo insertado."""
        resultado = ejecutar_reporte(db_connection, "inventario.sql", (901,))
        stocks = {r["codigo_producto"]: r["stock_actual"] for r in resultado}
        assert stocks["PROD-T01"] == Decimal("50.0000")
        assert stocks["PROD-T02"] == Decimal("3.0000")

    def test_bodega_sin_stock_retorna_lista_vacia(self, db_connection, seed_base):
        """Bodega sin registros de inventario debe retornar lista vacía, no error."""
        resultado = ejecutar_reporte(db_connection, "inventario.sql", (901,))
        assert resultado == []

    def test_no_incluye_productos_eliminados(self, db_connection, seed_inventario):
        """Productos con deleted_at no deben aparecer en el stock."""
        cur = db_connection.cursor()
        cur.execute("UPDATE productos SET deleted_at = NOW() WHERE id = 901")
        cur.close()
        resultado = ejecutar_reporte(db_connection, "inventario.sql", (901,))
        codigos = [r["codigo_producto"] for r in resultado]
        assert "PROD-T01" not in codigos


class TestProductosBajoMinimo:

    def test_detecta_producto_bajo_minimo(self, db_connection, seed_inventario):
        """
        DADO Producto 2 con stock=3 y mínimo=10
        CUANDO se consulta productos_bajo_minimo
        ENTONCES aparece solo Producto 2.
        """
        resultado = ejecutar_reporte(db_connection, "productos_bajo_minimo.sql", (901,))
        assert len(resultado) == 1
        assert resultado[0]["codigo_producto"] == "PROD-T02"

    def test_no_incluye_productos_con_stock_suficiente(self, db_connection, seed_inventario):
        """Producto 1 con stock=50 > mínimo=10 no debe aparecer."""
        resultado = ejecutar_reporte(db_connection, "productos_bajo_minimo.sql", (901,))
        codigos = [r["codigo_producto"] for r in resultado]
        assert "PROD-T01" not in codigos

    def test_sin_productos_bajo_minimo_retorna_vacio(self, db_connection, seed_base):
        """Bodega sin inventario: resultado vacío sin error."""
        resultado = ejecutar_reporte(db_connection, "productos_bajo_minimo.sql", (901,))
        assert resultado == []

    def test_stock_igual_a_minimo_no_aparece(self, db_connection, seed_inventario):
        """Stock exactamente igual al mínimo NO se considera bajo mínimo."""
        cur = db_connection.cursor()
        cur.execute("UPDATE inventario SET cantidad = 10.0000 WHERE id = 902")
        cur.close()
        resultado = ejecutar_reporte(db_connection, "productos_bajo_minimo.sql", (901,))
        assert resultado == []


class TestKardex:

    def test_numero_de_movimientos(self, db_connection, seed_kardex):
        """
        DADO 3 movimientos del Producto 1 en Bodega 901
        CUANDO se consulta el kardex para todo enero 2025
        ENTONCES retorna exactamente 3 filas.
        """
        resultado = ejecutar_reporte(
            db_connection, "kardex.sql",
            (901, 901, "2020-01-01", "2099-12-31")
        )
        assert len(resultado) == 3

    def test_saldo_final_cuadra(self, db_connection, seed_kardex):
        """El saldo posterior del último movimiento debe ser 35."""
        resultado = ejecutar_reporte(
            db_connection, "kardex.sql",
            (901, 901, "2020-01-01", "2099-12-31")
        )
        assert resultado[-1]["cantidad_posterior"] == Decimal("35.0000")

    def test_filtro_de_fecha_excluye_movimientos_fuera_de_rango(self, db_connection, seed_kardex):
        """Un rango de fechas en el pasado lejano no debe retornar ningún movimiento."""
        resultado = ejecutar_reporte(
            db_connection, "kardex.sql",
            (901, 901, "2000-01-01", "2000-01-31")
        )
        assert resultado == []

    def test_secuencia_de_saldos_es_coherente(self, db_connection, seed_kardex):
        """cantidad_posterior de cada fila debe ser = cantidad_anterior + cantidad (entrada) o - cantidad (salida)."""
        resultado = ejecutar_reporte(
            db_connection, "kardex.sql",
            (901, 901, "2020-01-01", "2099-12-31")
        )
        for r in resultado:
            if r["tipo_movimiento"] == "entrada":
                esperado = r["cantidad_anterior"] + r["cantidad"]
            else:
                esperado = r["cantidad_anterior"] - r["cantidad"]
            assert r["cantidad_posterior"] == pytest.approx(float(esperado), abs=0.0001)
