"""
Inserta datos mínimos en comercial_db para probar el ETL end-to-end.
Ejecutar UNA sola vez (verifica duplicados antes de insertar).
"""
from dotenv import load_dotenv
load_dotenv()
import os, mysql.connector

cfg = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME"),
}
conn = mysql.connector.connect(**cfg)
cur = conn.cursor()

def existe(tabla, id_val):
    cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE id = %s", (id_val,))
    return cur.fetchone()[0] > 0

print(f"Sembrando {cfg['database']}...")

if not existe("empresas", 1):
    cur.execute("INSERT INTO empresas (id,razon_social,ruc_rif,moneda) VALUES (1,'Comercial SA','1790000001001','USD')")

if not existe("sucursales", 1):
    cur.execute("INSERT INTO sucursales (id,id_empresa,nombre,codigo,estado) VALUES (1,1,'Sucursal Centro','S01',1)")
if not existe("sucursales", 2):
    cur.execute("INSERT INTO sucursales (id,id_empresa,nombre,codigo,estado) VALUES (2,1,'Sucursal Norte','S02',1)")

if not existe("bodegas", 1):
    cur.execute("INSERT INTO bodegas (id,id_sucursal,nombre,codigo,estado) VALUES (1,1,'Bodega Principal','B01',1)")
if not existe("bodegas", 2):
    cur.execute("INSERT INTO bodegas (id,id_sucursal,nombre,codigo,estado) VALUES (2,2,'Bodega Norte','B02',1)")

if not existe("unidades_medida", 1):
    cur.execute("INSERT INTO unidades_medida (id,nombre,abreviatura) VALUES (1,'Unidad','UN')")

if not existe("marcas", 1):
    cur.execute("INSERT INTO marcas (id,nombre) VALUES (1,'Marca A')")

if not existe("categorias", 1):
    cur.execute("INSERT INTO categorias (id,nombre) VALUES (1,'Electrónica')")
if not existe("categorias", 2):
    cur.execute("INSERT INTO categorias (id,nombre) VALUES (2,'Alimentos')")

for pid, cat, cod, nom in [(1,1,'P001','Laptop'),(2,1,'P002','Mouse'),(3,2,'P003','Arroz 1kg')]:
    if not existe("productos", pid):
        cur.execute("INSERT INTO productos (id,id_categoria,id_marca,id_unidad_medida,codigo,nombre,aplica_impuesto,porcentaje_impuesto,estado) VALUES (%s,%s,1,1,%s,%s,1,12.00,1)",(pid,cat,cod,nom))

for ppid, prod in [(1,1),(2,2),(3,3)]:
    if not existe("productos_presentaciones", ppid):
        cur.execute("INSERT INTO productos_presentaciones (id,id_producto,nombre,factor_conversion,estado) VALUES (%s,%s,'Unidad',1.0,1)",(ppid,prod))

for inv_id, prod, pres, bod, act, mn, mx in [
    (1,1,1,1,50,10,100),(2,2,2,1,200,20,300),(3,3,3,2,100,15,150),
]:
    if not existe("inventario", inv_id):
        cur.execute("INSERT INTO inventario (id,id_producto,id_presentacion,id_bodega,cantidad,cantidad_minima,cantidad_maxima) VALUES (%s,%s,%s,%s,%s,%s,%s)",(inv_id,prod,pres,bod,act,mn,mx))

if not existe("tipos_identificacion", 1):
    cur.execute("INSERT INTO tipos_identificacion (id,nombre,codigo) VALUES (1,'RUC','RUC')")

for tid, num, rs in [(1,'1790000001001','Cliente ABC'),(2,'1790000002001','Cliente XYZ'),(3,'1790000003001','Proveedor MNO')]:
    if not existe("terceros", tid):
        cur.execute("INSERT INTO terceros (id,id_tipo_identificacion,numero_identificacion,razon_social,estado) VALUES (%s,1,%s,%s,1)",(tid,num,rs))

for ttid, terc, tipo in [(1,1,'cliente'),(2,2,'cliente'),(3,3,'proveedor')]:
    if not existe("terceros_tipos", ttid):
        cur.execute("INSERT INTO terceros_tipos (id,id_tercero,tipo) VALUES (%s,%s,%s)",(ttid,terc,tipo))

# Movimientos de inventario
for mid, prod, pres, bod, tipo, cant, ant, post, costo in [
    (1,1,1,1,'entrada',50,0,50,800.00),
    (2,2,2,1,'entrada',200,0,200,25.00),
    (3,3,3,2,'entrada',100,0,100,1.50),
    (4,1,1,1,'salida',5,50,45,800.00),
    (5,2,2,1,'salida',10,200,190,25.00),
]:
    if not existe("movimientos_inventario", mid):
        cur.execute("INSERT INTO movimientos_inventario (id,id_producto,id_presentacion,id_bodega,tipo_movimiento,cantidad,cantidad_anterior,cantidad_posterior,costo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",(mid,prod,pres,bod,tipo,cant,ant,post,costo))

# Facturas (ventas)
for fid, num, fecha, venc, suc, cli, sub, desc, imp, tot, sal, est in [
    (1,'F-001','2026-01-15','2026-02-14',1,1,1000.00,0,120.00,1120.00,0,'pagada'),
    (2,'F-002','2026-01-20','2026-02-19',1,2,500.00,50,54.00,504.00,504.00,'pendiente'),
    (3,'F-003','2026-02-05','2026-03-07',2,1,2000.00,0,240.00,2240.00,0,'pagada'),
    (4,'F-004','2026-02-10','2026-03-12',1,1,300.00,0,36.00,336.00,336.00,'pendiente'),
    (5,'F-005','2026-03-01','2026-04-01',2,2,750.00,75,81.00,756.00,0,'pagada'),
]:
    if not existe("facturas", fid):
        cur.execute("INSERT INTO facturas (id,numero,fecha_emision,fecha_vencimiento,id_sucursal,id_cliente,subtotal,descuento,impuesto,total,saldo,estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(fid,num,fecha,venc,suc,cli,sub,desc,imp,tot,sal,est))

# Detalle facturas
# (id, factura, producto, presentacion, bodega, cantidad, precio_unit, subtotal, costo_unit)
for did, fac, prod, pres, bod, cant, precio, sub, costo in [
    (1, 1, 1, 1, 1,  1, 1000.00, 1000.00, 800.00),
    (2, 2, 2, 2, 1, 10,   50.00,  500.00,  25.00),
    (3, 3, 1, 1, 1,  2, 1000.00, 2000.00, 800.00),
    (4, 4, 3, 3, 2, 50,    6.00,  300.00,   1.50),
    (5, 5, 2, 2, 2, 15,   50.00,  750.00,  25.00),
]:
    if not existe("facturas_detalle", did):
        cur.execute(
            "INSERT INTO facturas_detalle "
            "(id,id_factura,id_producto,id_presentacion,id_bodega,cantidad,precio_unitario,subtotal,costo_unitario) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (did, fac, prod, pres, bod, cant, precio, sub, costo)
        )

# Órdenes de compra (id, sucursal, proveedor, bodega, numero, fecha, estado, total)
for oid, suc, prov, bod, num, fecha, est, tot in [
    (1, 1, 3, 1, 'OC-001', '2026-01-10', 'recibida',  40000.00),
    (2, 1, 3, 1, 'OC-002', '2026-02-01', 'recibida',   5000.00),
    (3, 2, 3, 2, 'OC-003', '2026-03-05', 'pendiente',   150.00),
]:
    if not existe("ordenes_compra", oid):
        cur.execute(
            "INSERT INTO ordenes_compra "
            "(id,id_sucursal,id_proveedor,id_bodega_destino,numero,fecha_emision,estado,total) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (oid, suc, prov, bod, num, fecha, est, tot)
        )

conn.commit()
cur.close()
conn.close()
print("Datos de prueba insertados OK")
