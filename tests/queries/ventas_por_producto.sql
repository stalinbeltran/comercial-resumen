-- ventas_por_producto(fecha_desde DATE, fecha_hasta DATE)
SELECT
    id_producto,
    codigo_producto,
    nombre_producto,
    categoria,
    SUM(cantidad)                                        AS total_unidades,
    SUM(subtotal)                                        AS total_venta,
    SUM(cantidad * costo_unitario)                       AS total_costo,
    SUM(subtotal) - SUM(cantidad * costo_unitario)       AS margen_bruto
FROM d_facturas_detalle
WHERE deleted_at IS NULL
  AND estado_factura <> 'anulada'
  AND fecha_emision BETWEEN %s AND %s
GROUP BY id_producto, codigo_producto, nombre_producto, categoria
ORDER BY total_venta DESC;
