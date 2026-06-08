-- kardex(id_producto INT, id_bodega INT, fecha_desde DATE, fecha_hasta DATE)
SELECT
    mi.created_at        AS fecha,
    mi.tipo_movimiento,
    mi.cantidad,
    mi.cantidad_anterior,
    mi.cantidad_posterior,
    mi.costo_unitario,
    mi.tipo_referencia,
    mi.id_referencia,
    mi.observacion
FROM movimientos_inventario mi
WHERE mi.deleted_at IS NULL
  AND mi.id_producto = %s
  AND mi.id_bodega   = %s
  AND DATE(mi.created_at) BETWEEN %s AND %s
ORDER BY mi.created_at ASC;
