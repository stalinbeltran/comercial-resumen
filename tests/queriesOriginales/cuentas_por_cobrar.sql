-- cuentas_por_cobrar(fecha_corte DATE)
-- Retorna facturas con saldo > 0 y su antigüedad en días a la fecha_corte
SELECT
    f.id                                                        AS id_factura,
    f.numero,
    f.fecha_emision,
    f.fecha_vencimiento,
    t.razon_social                                              AS cliente,
    f.total,
    f.saldo,
    DATEDIFF(%s, f.fecha_vencimiento)                           AS dias_vencido,
    CASE
        WHEN DATEDIFF(%s, f.fecha_vencimiento) <= 0  THEN 'vigente'
        WHEN DATEDIFF(%s, f.fecha_vencimiento) <= 30 THEN '1-30'
        WHEN DATEDIFF(%s, f.fecha_vencimiento) <= 60 THEN '31-60'
        WHEN DATEDIFF(%s, f.fecha_vencimiento) <= 90 THEN '61-90'
        ELSE '+90'
    END                                                         AS rango_antiguedad
FROM facturas f
JOIN terceros t ON t.id = f.id_cliente AND t.deleted_at IS NULL
WHERE f.deleted_at IS NULL
  AND f.estado NOT IN ('pagada', 'anulada')
  AND f.saldo > 0
  AND f.fecha_emision <= %s
ORDER BY dias_vencido DESC, t.razon_social;
