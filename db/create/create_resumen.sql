-- =============================================================================
-- Base de datos RESUMEN — comercial_resumen_db
-- Destino del ETL pandas (etl/pipeline.py).
-- Cada tabla r_* replica la estructura de su equivalente d_* de comercial_desn_db.
-- Se añade etl_runs para control de ejecuciones y watermarks.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS comercial_resumen_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE comercial_resumen_db;

-- =============================================================================
-- etl_runs — auditoría y control de watermarks del ETL
-- =============================================================================
CREATE TABLE IF NOT EXISTS etl_runs (
    id          INT           AUTO_INCREMENT PRIMARY KEY,
    tabla       VARCHAR(100)  NOT NULL,
    inicio      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fin         DATETIME      NULL,
    filas       INT           NULL,
    estado      ENUM('running', 'ok', 'error') NOT NULL DEFAULT 'running',
    watermark   DATETIME      NULL COMMENT 'updated_at máximo del último registro procesado',
    mensaje     TEXT          NULL,
    INDEX idx_tabla_estado (tabla, estado),
    INDEX idx_inicio       (inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- r_inventario
-- Origen: d_inventario (comercial_desn_db)
-- Estrategia ETL: full reload — TRUNCATE + INSERT (snapshot de stock)
-- =============================================================================
CREATE TABLE IF NOT EXISTS r_inventario (
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
-- r_movimientos_inventario
-- Origen: d_movimientos_inventario (comercial_desn_db)
-- Estrategia ETL: incremental — solo registros nuevos (append-only por naturaleza)
--                 watermark en campo fecha
-- =============================================================================
CREATE TABLE IF NOT EXISTS r_movimientos_inventario (
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
    tipo_referencia    VARCHAR(50)   NULL COMMENT 'factura, orden_compra, traslado, ajuste',
    id_referencia      INT           NULL,
    observacion        TEXT          NULL,
    created_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at         DATETIME      NULL,
    UNIQUE KEY uq_movimiento_orig (id_movimiento_orig),
    INDEX idx_producto_bodega    (id_producto, id_bodega),
    INDEX idx_fecha              (fecha),
    INDEX idx_bodega             (id_bodega)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- r_facturas
-- Origen: d_facturas (comercial_desn_db)
-- Estrategia ETL: UPSERT — estado y saldo pueden cambiar en registros existentes
-- =============================================================================
CREATE TABLE IF NOT EXISTS r_facturas (
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
    UNIQUE KEY uq_factura_orig   (id_factura_orig),
    INDEX idx_fecha_emision      (fecha_emision),
    INDEX idx_sucursal           (id_sucursal),
    INDEX idx_cliente            (id_cliente),
    INDEX idx_estado             (estado),
    INDEX idx_vencimiento        (fecha_vencimiento),
    INDEX idx_saldo_estado       (saldo, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- r_facturas_detalle
-- Origen: d_facturas_detalle (comercial_desn_db)
-- Estrategia ETL: incremental — solo registros nuevos (líneas no se modifican)
-- =============================================================================
CREATE TABLE IF NOT EXISTS r_facturas_detalle (
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
    id_categoria    INT           NULL COMMENT 'FK original: categorias.id',
    categoria       VARCHAR(100)  NULL,
    cantidad        DECIMAL(15,4) NOT NULL DEFAULT 0,
    subtotal        DECIMAL(15,2) NOT NULL DEFAULT 0,
    costo_unitario  DECIMAL(15,2) NOT NULL DEFAULT 0,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      DATETIME      NULL,
    UNIQUE KEY uq_detalle_orig (id_detalle_orig),
    INDEX idx_factura          (id_factura),
    INDEX idx_producto         (id_producto),
    INDEX idx_fecha            (fecha_emision),
    INDEX idx_estado           (estado_factura),
    INDEX idx_categoria        (id_categoria),
    INDEX idx_fecha_estado     (fecha_emision, estado_factura)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- r_ordenes_compra
-- Origen: d_ordenes_compra (comercial_desn_db)
-- Estrategia ETL: UPSERT — estado puede cambiar en registros existentes
-- =============================================================================
CREATE TABLE IF NOT EXISTS r_ordenes_compra (
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
    UNIQUE KEY uq_orden_orig (id_orden_orig),
    INDEX idx_proveedor      (id_proveedor),
    INDEX idx_fecha          (fecha_emision),
    INDEX idx_estado         (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
