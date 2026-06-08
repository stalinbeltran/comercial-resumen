-- ventas_por_producto(fecha_desde DATE, fecha_hasta DATE)
SELECT
    p.id                                                    AS id_producto,
    p.codigo                                                AS codigo_producto,
    p.nombre                                                AS nombre_producto,
    c.nombre                                                AS categoria,
    SUM(fd.cantidad)                                        AS total_unidades,
    SUM(fd.subtotal)                                        AS total_venta,
    SUM(fd.cantidad * fd.costo_unitario)                    AS total_costo,
    SUM(fd.subtotal) - SUM(fd.cantidad * fd.costo_unitario) AS margen_bruto
FROM facturas_detalle fd
JOIN facturas  f ON f.id = fd.id_factura  AND f.deleted_at IS NULL AND f.estado <> 'anulada'
JOIN productos p ON p.id = fd.id_producto AND p.deleted_at IS NULL
LEFT JOIN categorias c ON c.id = p.id_categoria AND c.deleted_at IS NULL
WHERE fd.deleted_at IS NULL
  AND f.fecha_emision BETWEEN %s AND %s
GROUP BY p.id, p.codigo, p.nombre, c.nombre
ORDER BY total_venta DESC;
