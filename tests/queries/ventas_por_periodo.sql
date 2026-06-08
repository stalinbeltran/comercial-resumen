-- ventas_por_periodo(fecha_desde DATE, fecha_hasta DATE, id_sucursal INT)
-- Pasa NULL en id_sucursal para todas las sucursales
SELECT
    id_factura_orig                                        AS id_factura,
    numero_factura,
    fecha_emision,
    sucursal,
    cliente,
    subtotal,
    descuento,
    impuesto,
    total,
    saldo
FROM d_facturas
WHERE deleted_at IS NULL
  AND estado <> 'anulada'
  AND fecha_emision BETWEEN %s AND %s
  AND (%s IS NULL OR id_sucursal = %s)
ORDER BY fecha_emision, numero_factura;
