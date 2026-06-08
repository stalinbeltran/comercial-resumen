"""
Tests del módulo de Tesorería.

Cubre:
  - Cuentas por cobrar con antigüedad correcta
  - Facturas pagadas excluidas del CxC
  - Rangos de antigüedad (vigente, 1-30, 31-60, 61-90, +90)
  - Cobros del período
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from tests.helpers.db_helpers import ejecutar_reporte, ejecutar_query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_cxc(db_connection, seed_base, seed_terceros):
    """
    Facturas con distintos estados de vencimiento al corte 2025-03-01:
      F-VIG  vence 2025-03-15  saldo=500  → vigente (no vencida)
      F-030  vence 2025-02-10  saldo=200  → 1-30 días (19 días al 2025-03-01)
      F-060  vence 2025-01-20  saldo=300  → 31-60 días (40 días al 2025-03-01)
      F-090  vence 2024-12-30  saldo=400  → 61-90 días (61 días al 2025-03-01)
      F-MAS  vence 2024-11-01  saldo=100  → +90 días (120 días al 2025-03-01)
      F-PAG  vence 2025-01-01  saldo=0    estado=pagada → no debe aparecer
    """
    cur = db_connection.cursor()
    facturas = [
        (901, 901, 901, 'F-VIG', '2025-01-10', '2025-03-15', 'activa',  500.00, 500.00),
        (902, 901, 901, 'F-030', '2025-01-10', '2025-02-10', 'activa',  200.00, 200.00),
        (903, 901, 901, 'F-060', '2025-01-10', '2025-01-20', 'activa',  300.00, 300.00),
        (904, 901, 901, 'F-090', '2024-12-01', '2024-12-30', 'vencida', 400.00, 400.00),
        (905, 901, 901, 'F-MAS', '2024-10-01', '2024-11-01', 'vencida', 100.00, 100.00),
        (906, 901, 901, 'F-PAG', '2025-01-01', '2025-02-01', 'pagada',  999.00, 0.00),
    ]
    cur.executemany("""
        INSERT INTO facturas
            (id, id_sucursal, id_cliente, numero, fecha_emision, fecha_vencimiento,
             estado, total, saldo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, facturas)
    cur.close()
    return {**seed_base, **seed_terceros}


@pytest.fixture
def seed_pagos_clientes(db_connection, seed_cxc, seed_formas_pago):
    """Cobros recibidos en enero 2025."""
    cur = db_connection.cursor()
    pagos = [
        (901, 901, 901, 901, '2025-01-15', 150.00),
        (902, 902, 901, 901, '2025-01-20', 200.00),
        (903, 903, 901, 901, '2025-01-28', 50.00),
    ]
    cur.executemany("""
        INSERT INTO pagos_clientes
            (id, id_factura, id_cliente, id_forma_pago, fecha_pago, monto)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, pagos)
    cur.close()
    return seed_cxc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCuentasPorCobrar:
    FECHA_CORTE = "2025-03-01"

    def _run(self, db_connection):
        return ejecutar_reporte(
            db_connection, "cuentas_por_cobrar.sql",
            (self.FECHA_CORTE,) * 6
        )

    def test_excluye_facturas_pagadas(self, db_connection, seed_cxc):
        """F-PAG (estado=pagada, saldo=0) no debe aparecer."""
        resultado = self._run(db_connection)
        numeros = [r["numero"] for r in resultado]
        assert "F-PAG" not in numeros

    def test_total_facturas_pendientes(self, db_connection, seed_cxc):
        """Deben aparecer 5 facturas con saldo > 0."""
        resultado = self._run(db_connection)
        assert len(resultado) == 5

    def test_rango_vigente(self, db_connection, seed_cxc):
        """F-VIG vence 2025-03-15 → al corte 2025-03-01 no está vencida → 'vigente'."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-VIG"]["rango_antiguedad"] == "vigente"

    def test_rango_1_30(self, db_connection, seed_cxc):
        """F-030 vence 2025-02-10 → 19 días vencida al corte → '1-30'."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-030"]["rango_antiguedad"] == "1-30"

    def test_rango_31_60(self, db_connection, seed_cxc):
        """F-060 vence 2025-01-20 → 40 días vencida al corte → '31-60'."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-060"]["rango_antiguedad"] == "31-60"

    def test_rango_61_90(self, db_connection, seed_cxc):
        """F-090 vence 2024-12-30 → 61 días vencida al corte → '61-90'."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-090"]["rango_antiguedad"] == "61-90"

    def test_rango_mas_90(self, db_connection, seed_cxc):
        """F-MAS vence 2024-11-01 → 120 días vencida al corte → '+90'."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-MAS"]["rango_antiguedad"] == "+90"

    def test_saldo_correcto(self, db_connection, seed_cxc):
        """El saldo de cada factura debe coincidir con lo insertado."""
        resultado = self._run(db_connection)
        por_numero = {r["numero"]: r for r in resultado}
        assert por_numero["F-VIG"]["saldo"] == Decimal("500.00")
        assert por_numero["F-MAS"]["saldo"] == Decimal("100.00")


class TestCobrosDelPeriodo:

    def test_total_cobros_enero(self, db_connection, seed_pagos_clientes):
        """
        DADO 3 cobros en enero 2025: 150 + 200 + 50 = 400
        CUANDO se suman los pagos del período
        ENTONCES total = 400.00
        """
        sql = """
            SELECT SUM(monto) AS total_cobrado, COUNT(*) AS num_cobros
            FROM pagos_clientes
            WHERE deleted_at IS NULL
              AND fecha_pago BETWEEN %s AND %s
        """
        resultado = ejecutar_query(
            db_connection, sql,
            ("2025-01-01", "2025-01-31")
        )
        assert resultado[0]["num_cobros"] == 3
        assert resultado[0]["total_cobrado"] == Decimal("400.00")

    def test_cobros_fuera_de_rango_excluidos(self, db_connection, seed_pagos_clientes):
        """Un período sin cobros debe retornar total NULL y 0 registros."""
        sql = """
            SELECT COUNT(*) AS num_cobros
            FROM pagos_clientes
            WHERE deleted_at IS NULL
              AND fecha_pago BETWEEN %s AND %s
        """
        resultado = ejecutar_query(
            db_connection, sql,
            ("2024-01-01", "2024-01-31")
        )
        assert resultado[0]["num_cobros"] == 0
