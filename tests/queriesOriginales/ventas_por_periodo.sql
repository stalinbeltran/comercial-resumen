-- ventas_por_periodo(fecha_desde DATE, fecha_hasta DATE, id_sucursal INT)
-- Pasa NULL en id_sucursal para todas las sucursales
SELECT
    f.id                                                AS id_factura,
    f.numero                                            AS numero_factura,
    f.fecha_emision,
    s.nombre                                            AS sucursal,
    t.razon_social                                      AS cliente,
    f.subtotal,
    f.descuento,
    f.impuesto,
    f.total,
    f.saldo
FROM facturas f
JOIN sucursales s ON s.id = f.id_sucursal AND s.deleted_at IS NULL
JOIN terceros   t ON t.id = f.id_cliente  AND t.deleted_at IS NULL
WHERE f.deleted_at IS NULL
  AND f.estado <> 'anulada'
  AND f.fecha_emision BETWEEN %s AND %s
  AND (%s IS NULL OR f.id_sucursal = %s)
ORDER BY f.fecha_emision, f.numero;
