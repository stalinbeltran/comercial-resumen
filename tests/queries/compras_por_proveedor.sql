-- compras_por_proveedor(fecha_desde DATE, fecha_hasta DATE)
SELECT
    id_proveedor,
    proveedor,
    COUNT(id)            AS num_ordenes,
    SUM(total)           AS total_comprado
FROM d_ordenes_compra
WHERE deleted_at IS NULL
  AND estado <> 'cancelada'
  AND fecha_emision BETWEEN %s AND %s
GROUP BY id_proveedor, proveedor
ORDER BY total_comprado DESC;
