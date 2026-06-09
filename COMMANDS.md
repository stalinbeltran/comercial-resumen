# Referencia de comandos — comercial-resumen

Guía de todos los comandos ejecutables del proyecto, agrupados por categoría.
Flujo de datos: `comercial_db` → `comercial_desn_db` → `comercial_resumen_db`.

---

## Flujo completo (orden de ejecución)

```bash
# 1. Crear esquemas de prueba
python _prepare_test_dbs.py

# 2. Sembrar datos mínimos de prueba en comercial_db
python _seed_test.py

# 3. Importar comercial_db → comercial_desn_db
python db/importar_desnormalizada.py

# 4. Importar comercial_desn_db → comercial_resumen_db (manual / sin ETL)
python db/importar_resumen.py

# 5. Ejecutar pipeline ETL completo
python run_etl.py

# 6. Correr todos los tests
pytest
```

---

## ETL — `run_etl.py`

Pipeline principal: `comercial_desn_db` → `comercial_resumen_db`.
Procesa las 5 tablas de resumen en paralelo (4 workers por defecto).

| Tabla | Estrategia | Watermark |
|---|---|---|
| r_inventario | Full reload | — |
| r_movimientos_inventario | Incremental | fecha |
| r_facturas | Upsert | updated_at |
| r_facturas_detalle | Incremental | updated_at |
| r_ordenes_compra | Upsert | updated_at |

```bash
# Ejecutar ETL completo (todas las tablas)
python run_etl.py

# Solo una tabla
python run_etl.py --tabla r_inventario
python run_etl.py --tabla r_facturas
python run_etl.py --tabla r_movimientos_inventario
python run_etl.py --tabla r_facturas_detalle
python run_etl.py --tabla r_ordenes_compra

# Varias tablas a la vez
python run_etl.py --tabla r_facturas --tabla r_ordenes_compra

# Dry-run: simula sin escribir en la BD
python run_etl.py --dry-run
python run_etl.py --tabla r_facturas --dry-run

# Controlar workers paralelos (default 4)
python run_etl.py --workers 1
python run_etl.py --workers 2

# Nivel de log (default INFO)
python run_etl.py --log-level DEBUG
python run_etl.py --log-level WARNING

# Combinaciones
python run_etl.py --tabla r_facturas --workers 1 --log-level DEBUG
python run_etl.py --dry-run --workers 2 --log-level DEBUG
```

---

## Importación capa desnormalizada — `db/importar_desnormalizada.py`

Importa de `comercial_db` → `comercial_desn_db` aplicando JOINs.
**Hace TRUNCATE de la tabla destino antes de cada carga** (idempotente).

```bash
# Importar todas las tablas
python db/importar_desnormalizada.py

# Solo una tabla
python db/importar_desnormalizada.py --tabla d_inventario
python db/importar_desnormalizada.py --tabla d_movimientos_inventario
python db/importar_desnormalizada.py --tabla d_facturas
python db/importar_desnormalizada.py --tabla d_facturas_detalle
python db/importar_desnormalizada.py --tabla d_ordenes_compra

# Tamaño de batch (default 500)
python db/importar_desnormalizada.py --batch-size 1000
python db/importar_desnormalizada.py --tabla d_facturas --batch-size 2000
```

---

## Importación capa resumen — `db/importar_resumen.py`

Importa de `comercial_desn_db` → `comercial_resumen_db`.
**Hace TRUNCATE de la tabla destino antes de cada carga** (idempotente).

```bash
# Importar todas las tablas
python db/importar_resumen.py

# Solo una tabla
python db/importar_resumen.py --tabla r_inventario
python db/importar_resumen.py --tabla r_movimientos_inventario
python db/importar_resumen.py --tabla r_facturas
python db/importar_resumen.py --tabla r_facturas_detalle
python db/importar_resumen.py --tabla r_ordenes_compra

# Tamaño de batch (default 500)
python db/importar_resumen.py --batch-size 1000
python db/importar_resumen.py --tabla r_facturas --batch-size 2000
```

---

## Preparación de bases de datos de prueba

### Crear esquemas de test

```bash
# Crea comercial_desn_test y comercial_resumen_test con DDL de db/create/
python _prepare_test_dbs.py
```

### Sembrar datos mínimos en comercial_db

```bash
# Inserta datos mínimos en comercial_db (idempotente — verifica duplicados)
python _seed_test.py
```

Datos que inserta: 1 empresa, 2 sucursales, 2 bodegas, 3 productos, 3 registros de inventario,
5 movimientos, 5 facturas, 5 detalles de factura, 3 órdenes de compra.

---

## Tests — pytest

Configurado en `pytest.ini`. Tests en `tests/`.

```bash
# Correr todos los tests
pytest

# Por módulo
pytest tests/reportes/
pytest tests/etl/
pytest tests/integracion/
pytest tests/etl/pipeline/

# Archivos específicos
pytest tests/reportes/test_ventas.py
pytest tests/reportes/test_inventario.py
pytest tests/reportes/test_compras.py
pytest tests/reportes/test_tesoreria.py
pytest tests/reportes/test_gerenciales.py
pytest tests/etl/test_extractores.py
pytest tests/etl/test_transformadores.py
pytest tests/etl/test_cargadores.py
pytest tests/etl/test_control.py
pytest tests/integracion/test_inventario.py
pytest tests/integracion/test_ventas.py

# Por marker
pytest -m unit          # tests sin BD (transformadores)
pytest -m integration   # tests contra BD de prueba
pytest -m pipeline      # tests end-to-end

# Test individual
pytest tests/etl/test_transformadores.py::TestTransformadorInventario::test_solo_columnas_destino

# Verbose + traceback largo
pytest -vv --tb=long

# Con cobertura
pytest --cov=etl --cov=db
pytest --cov=tests --cov-report=html

# Filtrar por nombre
pytest tests/ -k "test_etl"
pytest tests/ -k "inventario"
```

---

## Base de datos — operaciones directas MySQL

> **ADVERTENCIA:** Los siguientes comandos son destructivos e irreversibles.

### Crear bases de datos desde SQL

```bash
# Crear comercial_desn_db
mysql -u root -p < db/create/create_desnormalizada.sql

# Crear comercial_resumen_db
mysql -u root -p < db/create/create_resumen.sql
```

### Eliminar bases de datos completas

```bash
# Eliminar la BD desnormalizada (DESTRUCTIVO)
mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_desn_db;"

# Eliminar la BD resumen (DESTRUCTIVO)
mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_resumen_db;"

# Eliminar ambas BDs de test (DESTRUCTIVO)
mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_desn_test;"
mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_resumen_test;"
```

### Recrear BD desde cero

```bash
mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_desn_db;"
mysql -u root -p < db/create/create_desnormalizada.sql

mysql -u root -p -e "DROP DATABASE IF EXISTS comercial_resumen_db;"
mysql -u root -p < db/create/create_resumen.sql
```

### Ver estado de ejecuciones ETL (tabla de control)

```bash
mysql -u root -p comercial_resumen_db -e "SELECT * FROM etl_runs ORDER BY inicio DESC LIMIT 20;"
```

---

## Variables de entorno — `.env`

Copiar `.env.example` a `.env` y configurar:

```
# BD normalizada (fuente original)
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=comercial_db

# BD desnormalizada (intermedia)
DB_DESN_HOST=localhost
DB_DESN_PORT=3306
DB_DESN_USER=root
DB_DESN_PASSWORD=
DB_DESN_NAME=comercial_desn_db

# BD resumen (destino final)
DB_RESUMEN_HOST=localhost
DB_RESUMEN_PORT=3306
DB_RESUMEN_USER=root
DB_RESUMEN_PASSWORD=
DB_RESUMEN_NAME=comercial_resumen_db

# BDs de prueba (no tocar datos productivos)
DB_DESN_TEST_NAME=comercial_desn_test
DB_RESUMEN_TEST_NAME=comercial_resumen_test
```
