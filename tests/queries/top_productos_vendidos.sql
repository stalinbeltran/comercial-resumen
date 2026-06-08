-- top_productos_vendidos(fecha_desde DATE, fecha_hasta DATE, limite INT)
SELECT
    id_producto,
    codigo_producto,
    nombre_producto,
    SUM(cantidad)  AS total_unidades,
    SUM(subtotal)  AS total_venta
FROM d_facturas_detalle
WHERE deleted_at IS NULL
  AND estado_factura <> 'anulada'
  AND fecha_emision BETWEEN %s AND %s
GROUP BY id_producto, codigo_producto, nombre_producto
ORDER BY total_unidades DESC
LIMIT %s;
