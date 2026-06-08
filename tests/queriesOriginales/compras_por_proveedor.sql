-- compras_por_proveedor(fecha_desde DATE, fecha_hasta DATE)
SELECT
    t.id                    AS id_proveedor,
    t.razon_social          AS proveedor,
    COUNT(oc.id)            AS num_ordenes,
    SUM(oc.total)           AS total_comprado
FROM ordenes_compra oc
JOIN terceros t ON t.id = oc.id_proveedor AND t.deleted_at IS NULL
WHERE oc.deleted_at IS NULL
  AND oc.estado <> 'cancelada'
  AND oc.fecha_emision BETWEEN %s AND %s
GROUP BY t.id, t.razon_social
ORDER BY total_comprado DESC;
