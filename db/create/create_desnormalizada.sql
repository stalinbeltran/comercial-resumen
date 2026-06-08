-- =============================================================================
-- Base de datos DESNORMALIZADA — comercial_desn_db
-- Generado a partir de: tests/queriesOriginales/
-- Cada tabla consolida los JOINs del query original para eliminar joins
-- en tiempo de consulta. DB separada de la normalizada (ver .env).
-- =============================================================================

CREATE DATABASE IF NOT EXISTS comercial_desn_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE comercial_desn_db;

-- =============================================================================
-- d_inventario
-- Origen: inventario + productos + productos_presentaciones + bodegas
-- Queries:  inventario.sql, productos_bajo_minimo.sql
-- =============================================================================
CREATE TABLE IF NOT EXISTS d_inventario (
    id              INT           AUTO_INCREMENT PRIMARY KEY,
    id_producto     INT           NOT NULL COMMENT 'FK original: productos.id',
    codigo_producto VARCHAR(50)   NOT NULL,
    nombre_producto VARCHAR(200)  NOT NULL,
    id_presentacion INT           NOT NULL COMMENT 'FK original: productos_presentaciones.id',
    presentacion    VARCHAR(100)  NOT NULL,
    id_bodega       INT           NOT NULL COMMENT 'FK original: bodegas.id',
    bodega          VARCHAR(100)  NOT NULL,
    stock_actual    DECIMAL(15,4) NOT NULL DEFAULT 0,
    stock_minimo    DECIMAL(15,4) NOT NULL DEFAULT 0,
    stock_maximo    DECIMAL(15,4) NOT NULL DEFAULT 0,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      DATETIME      NULL,
    INDEX idx_bodega    (id_bodega),
    INDEX idx_producto  (id_producto),
    INDEX idx_stock_min (id_bodega, stock_actual, stock_minimo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- d_movimientos_inventario
-- Origen: movimientos_inventario + productos + bodegas
-- Queries:  kardex.sql
-- =============================================================================
CREATE TABLE IF NOT EXISTS d_movimientos_inventario (
    id                 INT           AUTO_INCREMENT PRIMARY KEY,
    id_movimiento_orig INT           NOT NULL COMMENT 'FK original: movimientos_inventario.id',
    id_producto        INT           NOT NULL COMMENT 'FK original: productos.id',
    codigo_producto    VARCHAR(50)   NOT NULL,
    nombre_producto    VARCHAR(200)  NOT NULL,
    id_bodega          INT           NOT NULL COMMENT 'FK original: bodegas.id',
    bodega             VARCHAR(100)  NOT NULL,
    fecha              DATETIME      NOT NULL,
    tipo_movimiento    VARCHAR(50)   NOT NULL COMMENT 'entrada, salida, traslado, ajuste',
    cantidad           DECIMAL(15,4) NOT NULL,
    cantidad_anterior  DECIMAL(15,4) NOT NULL,
    cantidad_posterior DECIMAL(15,4) NOT NULL,
    costo_unitario     DECIMAL(15,2) NOT NULL DEFAULT 0,
    tipo_referencia    VARCHAR(50)   NULL     COMMENT 'factura, orden_compra, traslado, ajuste',
    id_referencia      INT           NULL,
    observacion        TEXT          NULL,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at         DATETIME      NULL,
    INDEX idx_producto_bodega (id_producto, id_bodega),
    INDEX idx_fecha           (fecha),
    INDEX idx_bodega          (id_bodega)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- d_facturas
-- Origen: facturas + sucursales + terceros
-- Queries:  ventas_por_periodo.sql, cuentas_por_cobrar.sql
-- =============================================================================
CREATE TABLE IF NOT EXISTS d_facturas (
    id                INT           AUTO_INCREMENT PRIMARY KEY,
    id_factura_orig   INT           NOT NULL COMMENT 'FK original: facturas.id',
    numero_factura    VARCHAR(50)   NOT NULL,
    fecha_emision     DATE          NOT NULL,
    fecha_vencimiento DATE          NULL,
    id_sucursal       INT           NOT NULL COMMENT 'FK original: sucursales.id',
    sucursal          VARCHAR(100)  NOT NULL,
    id_cliente        INT           NOT NULL COMMENT 'FK original: terceros.id',
    cliente           VARCHAR(200)  NOT NULL,
    subtotal          DECIMAL(15,2) NOT NULL DEFAULT 0,
    descuento         DECIMAL(15,2) NOT NULL DEFAULT 0,
    impuesto          DECIMAL(15,2) NOT NULL DEFAULT 0,
    total             DECIMAL(15,2) NOT NULL DEFAULT 0,
    saldo             DECIMAL(15,2) NOT NULL DEFAULT 0,
    estado            VARCHAR(20)   NOT NULL COMMENT 'pendiente, pagada, anulada',
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at        DATETIME      NULL,
    INDEX idx_fecha_emision (fecha_emision),
    INDEX idx_sucursal      (id_sucursal),
    INDEX idx_cliente       (id_cliente),
    INDEX idx_estado        (estado),
    INDEX idx_vencimiento   (fecha_vencimiento),
    INDEX idx_saldo_estado  (saldo, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- d_facturas_detalle
-- Origen: facturas_detalle + facturas + productos + categorias
-- Queries:  ventas_por_producto.sql, top_productos_vendidos.sql
-- =============================================================================
CREATE TABLE IF NOT EXISTS d_facturas_detalle (
    id              INT           AUTO_INCREMENT PRIMARY KEY,
    id_detalle_orig INT           NOT NULL COMMENT 'FK original: facturas_detalle.id',
    id_factura      INT           NOT NULL COMMENT 'FK original: facturas.id',
    numero_factura  VARCHAR(50)   NOT NULL,
    fecha_emision   DATE          NOT NULL,
    id_sucursal     INT           NOT NULL COMMENT 'FK original: sucursales.id',
    estado_factura  VARCHAR(20)   NOT NULL COMMENT 'pendiente, pagada, anulada',
    id_producto     INT           NOT NULL COMMENT 'FK original: productos.id',
    codigo_producto VARCHAR(50)   NOT NULL,
    nombre_producto VARCHAR(200)  NOT NULL,
    id_categoria    INT           NULL     COMMENT 'FK original: categorias.id',
    categoria       VARCHAR(100)  NULL,
    cantidad        DECIMAL(15,4) NOT NULL DEFAULT 0,
    subtotal        DECIMAL(15,2) NOT NULL DEFAULT 0,
    costo_unitario  DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      DATETIME      NULL,
    INDEX idx_factura      (id_factura),
    INDEX idx_producto     (id_producto),
    INDEX idx_fecha        (fecha_emision),
    INDEX idx_estado       (estado_factura),
    INDEX idx_categoria    (id_categoria),
    INDEX idx_fecha_estado (fecha_emision, estado_factura)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- d_ordenes_compra
-- Origen: ordenes_compra + terceros
-- Queries:  compras_por_proveedor.sql
-- =============================================================================
CREATE TABLE IF NOT EXISTS d_ordenes_compra (
    id            INT           AUTO_INCREMENT PRIMARY KEY,
    id_orden_orig INT           NOT NULL COMMENT 'FK original: ordenes_compra.id',
    id_proveedor  INT           NOT NULL COMMENT 'FK original: terceros.id',
    proveedor     VARCHAR(200)  NOT NULL,
    fecha_emision DATE          NOT NULL,
    estado        VARCHAR(20)   NOT NULL COMMENT 'pendiente, aprobada, recibida, cancelada',
    total         DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at    DATETIME      NULL,
    INDEX idx_proveedor (id_proveedor),
    INDEX idx_fecha     (fecha_emision),
    INDEX idx_estado    (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
