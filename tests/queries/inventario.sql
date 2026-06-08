-- stock_por_bodega(id_bodega INT)
SELECT
    id_producto,
    codigo_producto,
    nombre_producto,
    presentacion,
    bodega,
    stock_actual,
    stock_minimo,
    stock_maximo
FROM d_inventario
WHERE deleted_at IS NULL
  AND id_bodega = %s
ORDER BY nombre_producto, presentacion;
