---
name: etl-profesional
description: >
  Skill para diseñar e implementar ETLs profesionales con pandas y SQLAlchemy sobre MySQL.
  Aplicar siempre que el usuario trabaje en procesos de extracción, transformación o carga de datos
  entre bases de datos, especialmente cuando el volumen de datos es grande. Activar ante menciones
  de: ETL, pipeline de datos, importar datos, carga masiva, resumen de datos, agregaciones,
  watermark, carga incremental, chunksize, to_sql, read_sql, comercial_desn_db, comercial_resumen_db.
---

# ETL Profesional con pandas — Skill de Referencia

Guía completa para construir ETLs robustos, eficientes y mantenibles con pandas + SQLAlchemy + MySQL.
Aplica a cualquier proceso de extracción desde `comercial_desn_db` hacia `comercial_resumen_db` (u otras BDs).

---

## Stack tecnológico

- **Extracción / Transformación**: pandas 2.x
- **Conexiones**: SQLAlchemy (obligatorio sobre mysql-connector-python)
- **Motor BD origen/destino**: MySQL vía `mysql+mysqlconnector`
- **Configuración**: python-dotenv (.env)
- **Logging**: módulo estándar `logging` con formato estructurado
- **Paralelismo**: `concurrent.futures.ThreadPoolExecutor` (I/O-bound)

---

## Regla #1 — Nunca `fetchall()` con volumen grande

```python
# MAL: carga todo en RAM antes de procesar
cursor.execute(query)
rows = cursor.fetchall()  # explota con millones de filas

# BIEN: streaming con chunksize
for chunk in pd.read_sql(query, engine_src, chunksize=10_000):
    procesar_y_cargar(chunk)
```

El `chunksize` en `pd.read_sql` hace cursor streaming real: nunca se materializa más de N filas en memoria simultáneamente. Valor recomendado: 5 000–20 000 según RAM disponible y ancho de columnas.

---

## Regla #2 — Siempre SQLAlchemy engine, nunca conexión DBAPI directa

```python
from sqlalchemy import create_engine, text
import os

def crear_engine(prefix: str = "") -> object:
    sep = f"_{prefix}" if prefix else ""
    url = (
        f"mysql+mysqlconnector://"
        f"{os.getenv(f'DB{sep}_USER')}:{os.getenv(f'DB{sep}_PASSWORD')}"
        f"@{os.getenv(f'DB{sep}_HOST', 'localhost')}"
        f":{os.getenv(f'DB{sep}_PORT', 3306)}"
        f"/{os.getenv(f'DB{sep}_NAME')}"
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)

engine_src = crear_engine("DESN")     # comercial_desn_db
engine_dst = crear_engine("RESUMEN")  # comercial_resumen_db
```

`pool_pre_ping=True` reconecta automáticamente si MySQL cierra la conexión por timeout (esencial en ETLs largos).

---

## Regla #3 — `to_sql` con `method="multi"` y `chunksize`

```python
df_resumen.to_sql(
    name="r_ventas_mensual",
    con=engine_dst,
    if_exists="append",    # nunca "replace" en producción
    index=False,
    chunksize=5_000,
    method="multi"         # INSERT multi-row: 10x–50x más rápido que el default
)
```

Para UPSERT (actualizar si ya existe):

```python
from sqlalchemy.dialects.mysql import insert as mysql_insert

def upsert(df, tabla, engine, cols_update):
    stmt = mysql_insert(tabla).values(df.to_dict("records"))
    update_dict = {c: stmt.inserted[c] for c in cols_update}
    stmt = stmt.on_duplicate_key_update(**update_dict)
    with engine.begin() as conn:
        conn.execute(stmt)
```

---

## Regla #4 — Tipado explícito para reducir RAM

pandas infiere `int64` (8 bytes) y `object` (puntero Python). Especificar tipos reduce el footprint 50–70 %:

```python
DTYPE_OPTIMIZADO = {
    "id_sucursal":      "int32",
    "id_producto":      "int32",
    "id_cliente":       "int32",
    "estado":           "category",   # baja cardinalidad → huge saving
    "tipo_movimiento":  "category",
    "nombre_producto":  "string",     # StringDtype, más eficiente que object
    "subtotal":         "float32",    # si precisión de 32-bit es suficiente
}

chunk = chunk.astype({k: v for k, v in DTYPE_OPTIMIZADO.items() if k in chunk.columns})
```

Regla de oro: columnas con cardinalidad < 50 valores únicos → `category`.

---

## Regla #5 — Estrategia de carga según tipo de tabla

| Tipo de tabla | Estrategia | Implementación |
|---|---|---|
| Dimensiones pequeñas (catálogos) | Full reload | TRUNCATE + INSERT |
| Hechos con histórico inmutable | Incremental por watermark | `WHERE updated_at > last_run` |
| Hechos que pueden cambiar (saldos, estados) | UPSERT / MERGE | `INSERT ... ON DUPLICATE KEY UPDATE` |
| Resúmenes calculados | Recálculo por período | DELETE período + INSERT recalculado |

### Watermark incremental

```python
def get_watermark(engine, tabla: str) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(watermark) FROM etl_runs WHERE tabla=:t AND estado='ok'"),
            {"t": tabla}
        ).fetchone()
    return str(row[0]) if row and row[0] else "1900-01-01 00:00:00"

def set_watermark(engine, tabla: str, watermark: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE etl_runs SET watermark=:w WHERE tabla=:t AND estado='ok' ORDER BY id DESC LIMIT 1"),
            {"w": watermark, "t": tabla}
        )
```

---

## Regla #6 — Tabla de control de ejecuciones (obligatoria)

```sql
CREATE TABLE IF NOT EXISTS etl_runs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    tabla       VARCHAR(100)  NOT NULL,
    inicio      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fin         DATETIME      NULL,
    filas       INT           NULL,
    estado      ENUM('running', 'ok', 'error') NOT NULL DEFAULT 'running',
    watermark   DATETIME      NULL     COMMENT 'último registro procesado exitosamente',
    mensaje     TEXT          NULL,
    INDEX idx_tabla_estado (tabla, estado)
);
```

Uso en el pipeline:

```python
def registrar_inicio(engine, tabla: str) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO etl_runs (tabla, estado) VALUES (:t, 'running')"), {"t": tabla}
        )
        return result.lastrowid

def registrar_fin(engine, run_id: int, filas: int, watermark: str = None, error: str = None):
    estado = "error" if error else "ok"
    with engine.begin() as conn:
        conn.execute(
            text("""UPDATE etl_runs
                    SET fin=NOW(), filas=:f, estado=:e, watermark=:w, mensaje=:m
                    WHERE id=:id"""),
            {"f": filas, "e": estado, "w": watermark, "m": error, "id": run_id}
        )
```

---

## Regla #7 — Atomicidad por tabla, no por ETL completo

Una sola transacción para millones de filas genera undo log enorme y riesgo de timeout.
Usar una transacción por chunk:

```python
for chunk in pd.read_sql(query, engine_src, chunksize=10_000):
    chunk_transformado = transformar(chunk)
    with engine_dst.begin() as conn:          # commit automático al salir
        chunk_transformado.to_sql(
            tabla, conn, if_exists="append",
            index=False, method="multi"
        )
```

---

## Regla #8 — Paralelismo para tablas independientes

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

log = logging.getLogger(__name__)

def ejecutar_en_paralelo(tablas: list, max_workers: int = 4):
    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(procesar_tabla, t): t for t in tablas}
        for fut in as_completed(futures):
            tabla = futures[fut]
            try:
                filas = fut.result()
                resultados[tabla] = ("ok", filas)
                log.info(f"[{tabla}] completada: {filas} filas")
            except Exception as exc:
                resultados[tabla] = ("error", str(exc))
                log.error(f"[{tabla}] ERROR: {exc}")
    return resultados
```

`ThreadPoolExecutor` es correcto aquí porque el trabajo es I/O-bound (espera de red/disco a MySQL). El GIL no es un obstáculo para I/O.

---

## Regla #9 — Logging estructurado con tiempos por etapa

```python
import logging, time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("etl")

class Timer:
    def __enter__(self):
        self._t = time.perf_counter()
        return self
    def __exit__(self, *_):
        self.elapsed = time.perf_counter() - self._t

# Uso
with Timer() as t:
    filas = cargar_tabla("r_ventas_mensual", df)
log.info(f"r_ventas_mensual: {filas} filas en {t.elapsed:.1f}s ({filas/t.elapsed:.0f} filas/s)")
```

---

## Regla #10 — Validación post-carga (reconciliación)

Después de cada tabla, verificar que los conteos coincidan:

```python
def validar_conteo(engine_src, query_cnt_src: str, engine_dst, tabla_dst: str, filtro: str = ""):
    cnt_src = pd.read_sql(query_cnt_src, engine_src).iloc[0, 0]
    cnt_dst = pd.read_sql(
        f"SELECT COUNT(*) FROM {tabla_dst} {filtro}", engine_dst
    ).iloc[0, 0]
    if cnt_src != cnt_dst:
        raise ValueError(f"Reconciliación fallida en {tabla_dst}: origen={cnt_src}, destino={cnt_dst}")
    return cnt_src
```

---

## Estructura de archivos recomendada

```
etl/
├── __init__.py
├── conexiones.py       # crear_engine() src y dst
├── control.py          # etl_runs: registrar_inicio/fin, get/set_watermark
├── extractores.py      # queries SQL por tabla fuente + read_sql chunked
├── transformadores.py  # lógica pandas de agregación/limpieza por tabla
├── cargadores.py       # to_sql, upsert, validar_conteo
├── pipeline.py         # orquestador: orden de tablas, manejo de errores, paralelismo
└── run_etl.py          # CLI entry point: argparse --tabla --desde --hasta --dry-run
```

---

## Checklist de calidad antes de poner en producción

- [ ] Extracción usa `chunksize`, nunca `fetchall()`
- [ ] Conexiones son SQLAlchemy engines con `pool_pre_ping=True`
- [ ] `to_sql` usa `method="multi"` y `chunksize`
- [ ] Tipos de columnas optimizados (`category` para enums, `int32` para IDs)
- [ ] Estrategia de carga definida por tabla (full/incremental/upsert)
- [ ] Tabla `etl_runs` registra inicio, fin, filas y watermark
- [ ] Transacciones por chunk, no por ETL completo
- [ ] Tablas independientes corren en paralelo
- [ ] Logging con tiempos por tabla y velocidad (filas/s)
- [ ] Validación de conteos post-carga
- [ ] Script CLI con `--dry-run` para validar sin escribir
- [ ] Variables de entorno en `.env`, nunca hardcodeadas

---

## Anti-patrones a evitar

| Anti-patrón | Consecuencia | Alternativa |
|---|---|---|
| `fetchall()` con millones de filas | OOM / crash | `chunksize` en `read_sql` |
| Una sola transacción para todo el ETL | Undo log enorme, timeout | Transacción por chunk |
| `if_exists="replace"` en producción | Borra la tabla y la recrea, pierde índices | `if_exists="append"` + TRUNCATE previo explícito |
| Credenciales hardcodeadas | Riesgo de seguridad | `.env` + `python-dotenv` |
| Sin tabla de control | No hay auditoría ni resumabilidad | `etl_runs` obligatoria |
| Columnas `object` sin optimizar | RAM 3–5x mayor de lo necesario | `astype()` con mapa de tipos |
| Full reload de tablas de hechos grandes | ETL lento, carga innecesaria | Incremental por watermark |
