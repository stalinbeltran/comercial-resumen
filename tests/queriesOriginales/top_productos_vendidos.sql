-- top_productos_vendidos(fecha_desde DATE, fecha_hasta DATE, limite INT)
SELECT
    p.id            AS id_producto,
    p.codigo        AS codigo_producto,
    p.nombre        AS nombre_producto,
    SUM(fd.cantidad) AS total_unidades,
    SUM(fd.subtotal) AS total_venta
FROM facturas_detalle fd
JOIN facturas  f ON f.id = fd.id_factura  AND f.deleted_at IS NULL AND f.estado <> 'anulada'
JOIN productos p ON p.id = fd.id_producto AND p.deleted_at IS NULL
WHERE fd.deleted_at IS NULL
  AND f.fecha_emision BETWEEN %s AND %s
GROUP BY p.id, p.codigo, p.nombre
ORDER BY total_unidades DESC
LIMIT %s;
