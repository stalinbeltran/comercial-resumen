-- productos_bajo_minimo(id_bodega INT)
SELECT
    id_producto,
    codigo_producto,
    nombre_producto,
    bodega,
    stock_actual,
    stock_minimo
FROM d_inventario
WHERE deleted_at IS NULL
  AND id_bodega = %s
  AND stock_actual < stock_minimo
ORDER BY (stock_minimo - stock_actual) DESC;
