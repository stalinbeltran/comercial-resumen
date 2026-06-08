---
name: empresa-comercial-db
description: >
  Skill para diseñar, implementar y probar una base de datos MySQL de empresa comercial típica
  con sucursales, bodegas, inventario, ventas, compras y tesorería. Usar siempre que el usuario
  trabaje en tablas, queries, reportes o pruebas relacionadas con este proyecto. Aplicar también
  cuando el usuario pida crear scripts Python de prueba (pytest), generar datos de prueba con
  faker, o construir consultas SQL para reportes operativos o gerenciales. Activar ante cualquier
  mención de módulos del proyecto: inventario, ventas, compras, clientes, proveedores, cartera,
  sucursales, bodegas, kardex, facturación o tesorería.
---

# Empresa Comercial DB — Skill de Referencia

Contexto completo del proyecto de base de datos para empresa comercial.
Úsalo como referencia para generar tablas, queries, reportes y pruebas consistentes.

---

## Stack tecnológico

- **Motor de BD**: MySQL
- **Cliente de administración**: DBeaver
- **Lenguaje de pruebas**: Python
- **Framework de pruebas**: pytest
- **Generador de datos ficticios**: faker
- **Comparación de resultados**: pandas
- **Conexión a MySQL**: mysql-connector-python o SQLAlchemy

---

## Convenciones globales de tablas

- Todas las tablas tienen: `id` INT AUTO_INCREMENT PRIMARY KEY, `created_at` DATETIME, `updated_at` DATETIME
- Soft delete con `deleted_at` DATETIME NULL (NULL = activo)
- Nombres de tablas en **snake_case plural** (ej. `ordenes_compra`)
- Nombres de columnas en **snake_case** (ej. `fecha_emision`)
- Claves foráneas nombradas como `id_<tabla_referenciada>` (ej. `id_sucursal`)
- Campos de estado usando VARCHAR o TINYINT con valores documentados en comentarios
- Montos monetarios como `DECIMAL(15,2)`
- Cantidades de inventario como `DECIMAL(15,4)` (permite fracciones)

---

## Módulos y tablas del proyecto

### Módulo: Organización
| Tabla | Descripción |
|---|---|
| `empresas` | Datos de la empresa (razón social, RUC/RIF, etc.) |
| `sucursales` | Sucursales o puntos de venta |
| `bodegas` | Almacenes, ligados a una sucursal |
| `areas` | Departamentos internos |
| `cargos` | Puestos de trabajo |
| `empleados` | Personal, ligado a cargo y área |

### Módulo: Productos e Inventario
| Tabla | Descripción |
|---|---|
| `unidades_medida` | kg, litro, unidad, caja, etc. |
| `marcas` | Fabricantes o marcas |
| `categorias` | Jerarquía padre-hijo de categorías |
| `productos` | Catálogo maestro |
| `productos_presentaciones` | Presentaciones del producto (unidad, caja, palet) |
| `inventario` | Stock por producto, presentación y bodega |
| `movimientos_inventario` | Kardex: entradas, salidas, traslados, ajustes |

### Módulo: Terceros
| Tabla | Descripción |
|---|---|
| `tipos_identificacion` | RUC, cédula, pasaporte, etc. |
| `terceros` | Tabla unificada de clientes y proveedores |
| `terceros_tipos` | Clasifica si es cliente, proveedor o ambos |
| `contactos` | Personas de contacto de un tercero |
| `direcciones` | Direcciones de terceros o sucursales |

### Módulo: Compras
| Tabla | Descripción |
|---|---|
| `ordenes_compra` | Cabecera de orden de compra |
| `ordenes_compra_detalle` | Líneas de productos |
| `recepciones` | Recepción de mercancía en bodega |
| `recepciones_detalle` | Productos recibidos por recepción |

### Módulo: Ventas
| Tabla | Descripción |
|---|---|
| `listas_precios` | Diferentes listas de precios |
| `listas_precios_detalle` | Precio por producto/presentación |
| `pedidos` | Pedidos de clientes (preventa) |
| `pedidos_detalle` | Líneas del pedido |
| `facturas` | Cabecera de factura de venta |
| `facturas_detalle` | Líneas de la factura |
| `notas_credito` | Devoluciones o ajustes a facturas |
| `notas_credito_detalle` | Detalle de la nota de crédito |

### Módulo: Tesorería
| Tabla | Descripción |
|---|---|
| `formas_pago` | Efectivo, tarjeta, transferencia, crédito |
| `cuentas_bancarias` | Cuentas propias de la empresa |
| `pagos_clientes` | Cobros recibidos |
| `pagos_proveedores` | Pagos realizados |
| `caja` | Movimientos de caja por sucursal |

### Módulo: Seguridad
| Tabla | Descripción |
|---|---|
| `usuarios` | Cuentas de acceso |
| `roles` | Admin, vendedor, bodeguero, etc. |
| `permisos` | Permisos por módulo/acción |
| `roles_permisos` | Relación roles ↔ permisos |
| `usuarios_roles` | Relación usuarios ↔ roles |
| `parametros` | Configuraciones generales |

---

## Reportes operativos implementados

### Inventario
- Stock actual por bodega
- Productos bajo mínimo
- Productos sin movimiento (N días)
- Valorización de inventario
- Kardex por producto
- Traslados entre bodegas
- Ajustes de inventario

### Compras
- Órdenes de compra por estado
- Compras por proveedor / por producto
- Comparativo de precios por proveedor
- Recepciones vs. órdenes (diferencias)
- Lead time por proveedor
- Cuentas por pagar con vencimientos

### Ventas
- Ventas por período (diario/semanal/mensual)
- Ventas por sucursal / por vendedor / por cliente
- Ventas por producto y categoría
- Pedidos pendientes de despacho
- Devoluciones y notas de crédito
- Cumplimiento de pedidos (completos vs. parciales)

### Tesorería
- Cuentas por cobrar
- Antigüedad de cartera (0-30, 31-60, 61-90, +90 días)
- Clientes en mora
- Cobros del período
- Cierre de caja por sucursal

### Gerenciales
- Dashboard ventas vs. meta
- Margen bruto por producto
- Rotación de inventario
- Top N productos más vendidos
- Comparativo de períodos

---

## Estrategia de pruebas con pytest

### Principio general
```
SETUP → insertar datos conocidos → EXECUTE consulta → ASSERT resultado esperado → TEARDOWN limpiar
```

### Stack
```
pytest                        # framework de pruebas
mysql-connector-python        # conexión MySQL
faker                         # datos ficticios realistas
pandas                        # comparación de resultados tabulares
```

### Estructura de carpetas
```
tests/
├── conftest.py               # conexión DB, fixtures globales
├── helpers/
│   └── db_helpers.py         # insertar y limpiar datos de prueba
├── data/
│   └── seeds/                # JSONs o SQLs con datos base reutilizables
├── reportes/
│   ├── test_inventario.py
│   ├── test_ventas.py
│   ├── test_compras.py
│   ├── test_tesoreria.py
│   └── test_gerenciales.py
└── queries/
    ├── inventario.sql        # queries separadas del código Python
    ├── ventas.sql
    └── ...
```

### Reglas de prueba
1. Usar base de datos separada `db_test`, NUNCA la productiva
2. Cada test es independiente (no depende del estado de otro)
3. Usar transacciones con rollback para no acumular basura
4. Las consultas SQL van en archivos `.sql` separados, no embebidas en Python
5. Parametrizar filtros (fechas, sucursal, producto) via fixtures

### Tipos de assertions por reporte
| Reporte | Qué verificar |
|---|---|
| Totales (ventas, compras) | Suma exacta de datos insertados |
| Rankings | Orden correcto y valores exactos |
| Filtros de fecha | Que no aparezcan registros fuera del rango |
| Inventario / kardex | entradas - salidas = saldo esperado |
| Cartera / antigüedad | Cada factura en el rango de días correcto |
| Sin datos | Lista vacía, no error |

### Niveles de prueba
- **Nivel 1**: Datos mínimos, resultado exacto y predecible
- **Nivel 2**: Casos borde (período vacío, múltiples facturas, multi-bodega)
- **Nivel 3** *(opcional)*: Volumen con faker (miles de registros, medir tiempo de respuesta)

### Patrón de test (ejemplo)
```python
def test_ventas_por_periodo(db_connection, seed_facturas):
    """
    DADO:   3 facturas en enero por 100, 200 y 300
    CUANDO: se ejecuta el reporte ventas_por_periodo para enero
    ENTONCES: total = 600, registros = 3
    """
    resultado = ejecutar_reporte(db_connection, "ventas_por_periodo",
                                  desde="2025-01-01", hasta="2025-01-31")
    assert len(resultado) == 3
    assert sum(r["total"] for r in resultado) == 600
```

### conftest.py — estructura base
```python
import pytest
import mysql.connector

@pytest.fixture(scope="session")
def db_connection():
    conn = mysql.connector.connect(
        host="localhost", user="test_user",
        password="test_pass", database="db_test"
    )
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def rollback(db_connection):
    db_connection.start_transaction()
    yield
    db_connection.rollback()
```

---

## Guías de generación de código

Al generar DDL (CREATE TABLE):
- Incluir siempre `created_at`, `updated_at`, `deleted_at`
- Agregar comentarios en columnas clave (`COMMENT 'valores: A=activo, I=inactivo'`)
- Definir índices en columnas usadas frecuentemente en WHERE y JOIN

Al generar queries de reportes:
- Siempre filtrar `deleted_at IS NULL`
- Usar aliases descriptivos en columnas (`SUM(fd.cantidad * fd.precio_unitario) AS total_venta`)
- Parametrizar fechas con placeholders (`%s` para mysql-connector, `:fecha` para SQLAlchemy)
- Incluir ORDER BY explícito

Al generar seeds de prueba:
- Usar IDs fijos y conocidos (no auto-generados) para poder hacer assertions exactos
- Crear el mínimo de registros necesario para probar el escenario
- Nombrar fixtures por el módulo + escenario (`seed_facturas_enero`, `seed_stock_minimo`)
