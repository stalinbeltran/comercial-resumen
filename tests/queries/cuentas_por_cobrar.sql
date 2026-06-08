-- cuentas_por_cobrar(fecha_corte DATE)
-- Retorna facturas con saldo > 0 y su antigüedad en días a la fecha_corte
SELECT
    id_factura_orig                                             AS id_factura,
    numero_factura                                              AS numero,
    fecha_emision,
    fecha_vencimiento,
    cliente,
    total,
    saldo,
    DATEDIFF(%s, fecha_vencimiento)                             AS dias_vencido,
    CASE
        WHEN DATEDIFF(%s, fecha_vencimiento) <= 0  THEN 'vigente'
        WHEN DATEDIFF(%s, fecha_vencimiento) <= 30 THEN '1-30'
        WHEN DATEDIFF(%s, fecha_vencimiento) <= 60 THEN '31-60'
        WHEN DATEDIFF(%s, fecha_vencimiento) <= 90 THEN '61-90'
        ELSE '+90'
    END                                                         AS rango_antiguedad
FROM d_facturas
WHERE deleted_at IS NULL
  AND estado NOT IN ('pagada', 'anulada')
  AND saldo > 0
  AND fecha_emision <= %s
ORDER BY dias_vencido DESC, cliente;
