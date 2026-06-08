-- kardex(id_producto INT, id_bodega INT, fecha_desde DATE, fecha_hasta DATE)
SELECT
    fecha,
    tipo_movimiento,
    cantidad,
    cantidad_anterior,
    cantidad_posterior,
    costo_unitario,
    tipo_referencia,
    id_referencia,
    observacion
FROM d_movimientos_inventario
WHERE deleted_at IS NULL
  AND id_producto = %s
  AND id_bodega   = %s
  AND DATE(fecha) BETWEEN %s AND %s
ORDER BY fecha ASC;
