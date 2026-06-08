-- stock_por_bodega(id_bodega INT)
SELECT
    p.id                                        AS id_producto,
    p.codigo                                    AS codigo_producto,
    p.nombre                                    AS nombre_producto,
    pp.nombre                                   AS presentacion,
    b.nombre                                    AS bodega,
    i.cantidad                                  AS stock_actual,
    i.cantidad_minima                           AS stock_minimo,
    i.cantidad_maxima                           AS stock_maximo
FROM inventario i
JOIN productos              p  ON p.id  = i.id_producto    AND p.deleted_at  IS NULL
JOIN productos_presentaciones pp ON pp.id = i.id_presentacion AND pp.deleted_at IS NULL
JOIN bodegas                b  ON b.id  = i.id_bodega      AND b.deleted_at  IS NULL
WHERE i.deleted_at IS NULL
  AND i.id_bodega = %s
ORDER BY p.nombre, pp.nombre;
