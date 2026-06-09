---
name: etl-tests
description: >
  Skill para diseñar e implementar tests profesionales de ETLs pandas+SQLAlchemy sobre MySQL.
  Aplicar cuando el usuario trabaje en pruebas del ETL comercial_desn_db → comercial_resumen_db,
  o en cualquier test que involucre: extractores, transformadores, cargadores, pipeline,
  etl_runs, watermarks, full reload, incremental, upsert. Activar ante menciones de:
  pytest ETL, test de pipeline, test de transformadores, test de cargadores, test incremental,
  test upsert, test watermark, conftest ETL, fixtures de BD de prueba.
---

# Tests Profesionales de ETL — Skill de Referencia

Guía completa para probar ETLs pandas+SQLAlchemy con pytest y MySQL real.
Aplica al proyecto comercial_desn_db → comercial_resumen_db.

---

## Principio fundamental: ETL no admite rollback

Los tests de ETL **no pueden usar** `db_connection.rollback()` como teardown.
El pipeline interno hace `engine.begin()` → commit por chunk, que no se puede revertir
con rollback de la conexión de prueba.

**La única estrategia correcta es TRUNCATE antes de cada test.**

```python
@pytest.fixture(autouse=True)
def limpiar_destino(engine_resumen_test):
    tablas = [
        "etl_runs", "r_inventario", "r_facturas",
        "r_facturas_detalle", "r_movimientos_inventario", "r_ordenes_compra",
    ]
    with engine_resumen_test.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in tablas:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield
```

---

## Stack de pruebas

```
pytest                    # framework
sqlalchemy                # engines de test (apuntan a BDs de prueba)
pandas                    # assertions de DataFrames
mysql-connector-python    # driver
python-dotenv             # .env con DB_DESN_TEST_NAME, DB_RESUMEN_TEST_NAME
```

---

## Variables de entorno para test

Agregar al `.env`:
```
DB_DESN_TEST_NAME=comercial_desn_test
DB_RESUMEN_TEST_NAME=comercial_resumen_test
```

Los engines de test se construyen **dentro de conftest.py**, NUNCA se importan
de `etl/conexiones.py` (esos apuntan a producción).

---

## conftest.py base para tests ETL

```python
import os
import pytest
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def _engine_test(name_env: str):
    pw  = quote_plus(os.getenv("DB_DESN_PASSWORD", os.getenv("DB_PASSWORD", "")))
    url = (
        f"mysql+mysqlconnector://{os.getenv('DB_DESN_USER', 'root')}:{pw}"
        f"@{os.getenv('DB_DESN_HOST', 'localhost')}"
        f":{os.getenv('DB_DESN_PORT', '3306')}"
        f"/{os.getenv(name_env)}"
    )
    return create_engine(url, pool_pre_ping=True)

@pytest.fixture(scope="session")
def engine_src():
    return _engine_test("DB_DESN_TEST_NAME")

@pytest.fixture(scope="session")
def engine_dst():
    return _engine_test("DB_RESUMEN_TEST_NAME")

@pytest.fixture(autouse=True)
def limpiar_fuente(engine_src):
    tablas_src = [
        "d_facturas_detalle", "d_facturas",
        "d_movimientos_inventario", "d_inventario", "d_ordenes_compra",
    ]
    with engine_src.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in tablas_src:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield

@pytest.fixture(autouse=True)
def limpiar_destino(engine_dst):
    tablas_dst = [
        "etl_runs", "r_inventario", "r_facturas",
        "r_facturas_detalle", "r_movimientos_inventario", "r_ordenes_compra",
    ]
    with engine_dst.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in tablas_dst:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield
```

---

## Patrón base de cada test

```
DADO   →  insertar filas conocidas en la BD fuente de test
CUANDO →  llamar al procesador del pipeline con los engines de test
ENTONCES → leer la BD destino de test y hacer assertions exactas
```

Los datos de prueba deben ser:
- **Fijos** (IDs hardcodeados, fechas fijas) — nunca random
- **Mínimos** — solo los registros necesarios para el escenario
- **Descriptivos** — el nombre del fixture describe el escenario (`facturas_enero_una_sucursal`)

---

## Niveles de prueba

### Nivel 1 — Unit (sin BD)

Solo `transformadores.py`. Son funciones puras pandas → pandas.

```python
def test_transformar_facturas_convierte_fecha_a_date():
    df = pd.DataFrame({...})
    out = tr.transformar_facturas(df)
    assert isinstance(out["fecha_emision"].iloc[0], date)

def test_transformar_facturas_categoria_queda_como_str():
    df["estado"] = df["estado"].astype("category")
    out = tr.transformar_facturas(df)
    assert out["estado"].dtype == object  # MySQL no acepta CategoricalDtype
```

### Nivel 2 — Integración por módulo (con BD de test)

Probar extractores, cargadores y control por separado:

```python
# test_extractores.py
def test_leer_facturas_respeta_watermark(engine_src):
    insertar_facturas(engine_src, updated_at="2026-01-01 10:00:00")
    chunks = list(ext.leer_facturas("2026-01-01 10:00:00"))  # exactamente = watermark
    total = sum(len(c) for c in chunks)
    assert total == 0  # watermark usa >, no >=

# test_cargadores.py
def test_upsert_actualiza_campo_mutable(engine_dst):
    insertar_r_factura(engine_dst, id_factura_orig=1, saldo=100.00)
    df_nuevo = pd.DataFrame([{..., "id_factura_orig": 1, "saldo": 0.00, ...}])
    carg.upsert(df_nuevo, "r_facturas", COLS_UPDATE)
    saldo_actual = leer_saldo(engine_dst, id_factura_orig=1)
    assert saldo_actual == 0.00
```

### Nivel 3 — End-to-end por estrategia (pipeline completo)

Llaman al procesador completo (`_proc_facturas`, etc.) con engines parcheados:

```python
def test_pipeline_facturas_primera_corrida(engine_src, engine_dst, monkeypatch):
    # Parchear engines para que el pipeline use las BDs de test
    monkeypatch.setattr("etl.conexiones.engine_desn",    engine_src)
    monkeypatch.setattr("etl.conexiones.engine_resumen", engine_dst)

    insertar_facturas(engine_src, n=3)
    from etl.pipeline import _proc_facturas
    filas = _proc_facturas(dry_run=False)

    assert filas == 3
    assert contar(engine_dst, "r_facturas") == 3
    assert ultimo_run_ok(engine_dst, "r_facturas")
```

---

## Escenarios obligatorios por estrategia

### Full reload (r_inventario)
- [ ] N filas en fuente → exactamente N en destino
- [ ] Segunda corrida sin cambios → destino sigue con N (no duplica)
- [ ] Fuente vacía → destino queda vacío (TRUNCATE funcionó)
- [ ] Fila con `deleted_at IS NOT NULL` en fuente → **no** llega a destino

### Incremental (r_movimientos_inventario, r_facturas_detalle)
- [ ] Primera corrida: todos los registros se cargan
- [ ] Segunda corrida sin nuevos: 0 filas, watermark no retrocede
- [ ] Registro nuevo (updated_at > watermark): solo ese llega
- [ ] Registro con updated_at == watermark exacto: **no** se reprocesa (`>` no `>=`)
- [ ] `deleted_at` no NULL post-watermark: **no** llega a destino

### UPSERT (r_facturas, r_ordenes_compra)
- [ ] Registro nuevo: se inserta
- [ ] Registro existente con campo mutable cambiado: se actualiza en destino
- [ ] Registro existente sin cambios: se re-escribe igual (idempotente)
- [ ] `deleted_at` poblado en una actualización: se propaga

### etl_runs (control)
- [ ] `registrar_inicio` crea fila con estado='running'
- [ ] `registrar_fin` ok: actualiza estado, filas, watermark, fin
- [ ] `registrar_fin` error: estado='error', mensaje poblado
- [ ] `get_watermark` sin corrida previa: retorna '1900-01-01 00:00:00'
- [ ] `get_watermark` con corrida exitosa: retorna el watermark de la última

---

## Helpers reutilizables

Centralizar la inserción de datos de prueba en `tests/etl/helpers.py`:

```python
def insertar_d_facturas(engine, filas: list[dict]) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO d_facturas (...) VALUES (...)"), filas)

def contar(engine, tabla: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()

def leer_tabla(engine, tabla: str) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {tabla}", engine)

def ultimo_run(engine, tabla: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM etl_runs WHERE tabla=:t ORDER BY id DESC LIMIT 1"),
            {"t": tabla}
        ).mappings().fetchone()
    return dict(row) if row else {}
```

---

## Estructura de carpetas

```
tests/
└── etl/
    ├── conftest.py                    # engines test, limpiar_fuente, limpiar_destino
    ├── helpers.py                     # insertar_*, contar(), leer_tabla(), ultimo_run()
    ├── test_transformadores.py        # unit — sin BD, puro pandas
    ├── test_extractores.py            # integración — lectura de fuente
    ├── test_cargadores.py             # integración — escritura en destino
    ├── test_control.py                # etl_runs auditoría
    └── pipeline/
        ├── __init__.py
        ├── test_inventario.py         # full reload
        ├── test_facturas.py           # upsert
        ├── test_facturas_detalle.py   # incremental
        ├── test_movimientos.py        # incremental
        └── test_ordenes_compra.py     # upsert
```

---

## Reglas de escritura de tests

1. **Nombre descriptivo**: `test_<módulo>_<escenario>_<resultado_esperado>`
   - Bien: `test_incremental_no_duplica_en_segunda_corrida`
   - Mal: `test_etl_ok`

2. **Un solo assert por escenario lógico** — si necesitas varios, usa `assert` seguidos sin lógica entre ellos.

3. **Sin lógica de negocio en el test** — la lógica está en el helper. El test solo orquesta.

4. **Docstring obligatorio** con patrón DADO/CUANDO/ENTONCES en los tests de pipeline.

5. **IDs fijos y bajos** (1, 2, 3) — nunca auto-generados ni random.

6. **Fechas fijas absolutas** — `"2026-01-15"`, nunca `date.today()` (los tests deben ser deterministas).

---

## Anti-patrones prohibidos

| Anti-patrón | Consecuencia |
|---|---|
| `rollback()` como teardown del ETL | Los commits internos del pipeline no se revierten |
| Importar engines de `etl.conexiones` | Apuntan a la BD productiva |
| Usar Faker sin seed fijo | Assertions de valor exacto imposibles |
| Tests que dependen de orden de ejecución | Un fallo rompe la cadena |
| Mock del engine en lugar de BD real | Bugs de tipo/NULL/encoding solo aparecen con MySQL real |
| `assert len(df) > 0` | No verifica valores, solo existencia |
