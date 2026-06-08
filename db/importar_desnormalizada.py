"""
Importación de datos desde comercial_db → comercial_desn_db.

Para cada tabla d_* hace TRUNCATE + INSERT en lotes (re-importación limpia).
Las queries de extracción replican los JOINs de tests/queriesOriginales/ pero
sin filtros parametrizados, para volcar la totalidad de los datos.

Uso:
    python db/importar_desnormalizada.py
    python db/importar_desnormalizada.py --tabla d_inventario
    python db/importar_desnormalizada.py --batch-size 1000
"""
import argparse
import os
import sys
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Conexiones
# ---------------------------------------------------------------------------

def _conn(prefix: str = "") -> mysql.connector.MySQLConnection:
    sep = "_DESN" if prefix else ""
    cfg = {
        "host":     os.getenv(f"DB{sep}_HOST", "localhost"),
        "port":     int(os.getenv(f"DB{sep}_PORT", 3306)),
        "user":     os.getenv(f"DB{sep}_USER", "root"),
        "password": os.getenv(f"DB{sep}_PASSWORD", ""),
        "database": os.getenv(f"DB{sep}_NAME"),
    }
    if not cfg["database"]:
        print(f"ERROR: DB{sep}_NAME no está definido en .env", file=sys.stderr)
        sys.exit(1)
    return mysql.connector.connect(**cfg)


# ---------------------------------------------------------------------------
# Queries de extracción — full-scan, sin filtros de parámetro
# Derivadas de tests/queriesOriginales/ añadiendo los IDs que faltan en los
# queries originales (pensados para reportes, no para ETL).
# ---------------------------------------------------------------------------

SQL_EXTRACT: dict[str, str] = {

    # inventario.sql + productos_bajo_minimo.sql
    # Los queries originales filtran por id_bodega; aquí extraemos todo.
    "d_inventario": """
        SELECT
            i.id_producto,
            p.codigo                AS codigo_producto,
            p.nombre                AS nombre_producto,
            i.id_presentacion,
            pp.nombre               AS presentacion,
            i.id_bodega,
            b.nombre                AS bodega,
            i.cantidad              AS stock_actual,
            i.cantidad_minima       AS stock_minimo,
            i.cantidad_maxima       AS stock_maximo
        FROM inventario i
        JOIN productos               p  ON p.id  = i.id_producto     AND p.deleted_at  IS NULL
        JOIN productos_presentaciones pp ON pp.id = i.id_presentacion AND pp.deleted_at IS NULL
        JOIN bodegas                 b  ON b.id  = i.id_bodega       AND b.deleted_at  IS NULL
        WHERE i.deleted_at IS NULL
        ORDER BY p.nombre, pp.nombre
    """,

    # kardex.sql — el original no tiene JOINs; se agregan aquí para obtener
    # nombre/codigo de producto y bodega que requiere d_movimientos_inventario.
    "d_movimientos_inventario": """
        SELECT
            mi.id                   AS id_movimiento_orig,
            mi.id_producto,
            p.codigo                AS codigo_producto,
            p.nombre                AS nombre_producto,
            mi.id_bodega,
            b.nombre                AS bodega,
            mi.created_at           AS fecha,
            mi.tipo_movimiento,
            mi.cantidad,
            mi.cantidad_anterior,
            mi.cantidad_posterior,
            mi.costo_unitario,
            mi.tipo_referencia,
            mi.id_referencia,
            mi.observacion
        FROM movimientos_inventario mi
        JOIN productos p ON p.id = mi.id_producto AND p.deleted_at IS NULL
        JOIN bodegas   b ON b.id = mi.id_bodega   AND b.deleted_at IS NULL
        WHERE mi.deleted_at IS NULL
        ORDER BY mi.created_at ASC
    """,

    # ventas_por_periodo.sql + cuentas_por_cobrar.sql
    # Los originales no traen todos los campos (estado, fecha_vencimiento, IDs).
    "d_facturas": """
        SELECT
            f.id                    AS id_factura_orig,
            f.numero                AS numero_factura,
            f.fecha_emision,
            f.fecha_vencimiento,
            f.id_sucursal,
            s.nombre                AS sucursal,
            f.id_cliente,
            t.razon_social          AS cliente,
            f.subtotal,
            f.descuento,
            f.impuesto,
            f.total,
            f.saldo,
            f.estado
        FROM facturas f
        JOIN sucursales s ON s.id = f.id_sucursal AND s.deleted_at IS NULL
        JOIN terceros   t ON t.id = f.id_cliente  AND t.deleted_at IS NULL
        WHERE f.deleted_at IS NULL
        ORDER BY f.fecha_emision, f.numero
    """,

    # ventas_por_producto.sql + top_productos_vendidos.sql
    # Ambos originales son agregados (GROUP BY). Aquí se extrae a nivel de fila
    # para que d_facturas_detalle permita cualquier agrupación posterior.
    "d_facturas_detalle": """
        SELECT
            fd.id                   AS id_detalle_orig,
            fd.id_factura,
            f.numero                AS numero_factura,
            f.fecha_emision,
            f.id_sucursal,
            f.estado                AS estado_factura,
            fd.id_producto,
            p.codigo                AS codigo_producto,
            p.nombre                AS nombre_producto,
            p.id_categoria,
            c.nombre                AS categoria,
            fd.cantidad,
            fd.subtotal,
            fd.costo_unitario
        FROM facturas_detalle fd
        JOIN facturas  f ON f.id = fd.id_factura  AND f.deleted_at IS NULL
        JOIN productos p ON p.id = fd.id_producto AND p.deleted_at IS NULL
        LEFT JOIN categorias c ON c.id = p.id_categoria AND c.deleted_at IS NULL
        WHERE fd.deleted_at IS NULL
        ORDER BY f.fecha_emision, fd.id_factura, fd.id
    """,

    # compras_por_proveedor.sql — el original es agregado por proveedor.
    # Aquí se extrae una fila por orden para preservar id_orden_orig y estado.
    "d_ordenes_compra": """
        SELECT
            oc.id                   AS id_orden_orig,
            oc.id_proveedor,
            t.razon_social          AS proveedor,
            oc.fecha_emision,
            oc.estado,
            oc.total
        FROM ordenes_compra oc
        JOIN terceros t ON t.id = oc.id_proveedor AND t.deleted_at IS NULL
        WHERE oc.deleted_at IS NULL
        ORDER BY oc.fecha_emision
    """,
}


# ---------------------------------------------------------------------------
# INSERT statements — columnas en el mismo orden que los SELECT de arriba
# ---------------------------------------------------------------------------

SQL_INSERT: dict[str, str] = {

    "d_inventario": """
        INSERT INTO d_inventario
            (id_producto, codigo_producto, nombre_producto,
             id_presentacion, presentacion,
             id_bodega, bodega,
             stock_actual, stock_minimo, stock_maximo)
        VALUES
            (%(id_producto)s, %(codigo_producto)s, %(nombre_producto)s,
             %(id_presentacion)s, %(presentacion)s,
             %(id_bodega)s, %(bodega)s,
             %(stock_actual)s, %(stock_minimo)s, %(stock_maximo)s)
    """,

    "d_movimientos_inventario": """
        INSERT INTO d_movimientos_inventario
            (id_movimiento_orig,
             id_producto, codigo_producto, nombre_producto,
             id_bodega, bodega,
             fecha, tipo_movimiento,
             cantidad, cantidad_anterior, cantidad_posterior,
             costo_unitario, tipo_referencia, id_referencia, observacion)
        VALUES
            (%(id_movimiento_orig)s,
             %(id_producto)s, %(codigo_producto)s, %(nombre_producto)s,
             %(id_bodega)s, %(bodega)s,
             %(fecha)s, %(tipo_movimiento)s,
             %(cantidad)s, %(cantidad_anterior)s, %(cantidad_posterior)s,
             %(costo_unitario)s, %(tipo_referencia)s, %(id_referencia)s, %(observacion)s)
    """,

    "d_facturas": """
        INSERT INTO d_facturas
            (id_factura_orig, numero_factura,
             fecha_emision, fecha_vencimiento,
             id_sucursal, sucursal,
             id_cliente, cliente,
             subtotal, descuento, impuesto, total, saldo,
             estado)
        VALUES
            (%(id_factura_orig)s, %(numero_factura)s,
             %(fecha_emision)s, %(fecha_vencimiento)s,
             %(id_sucursal)s, %(sucursal)s,
             %(id_cliente)s, %(cliente)s,
             %(subtotal)s, %(descuento)s, %(impuesto)s, %(total)s, %(saldo)s,
             %(estado)s)
    """,

    "d_facturas_detalle": """
        INSERT INTO d_facturas_detalle
            (id_detalle_orig, id_factura, numero_factura,
             fecha_emision, id_sucursal, estado_factura,
             id_producto, codigo_producto, nombre_producto,
             id_categoria, categoria,
             cantidad, subtotal, costo_unitario)
        VALUES
            (%(id_detalle_orig)s, %(id_factura)s, %(numero_factura)s,
             %(fecha_emision)s, %(id_sucursal)s, %(estado_factura)s,
             %(id_producto)s, %(codigo_producto)s, %(nombre_producto)s,
             %(id_categoria)s, %(categoria)s,
             %(cantidad)s, %(subtotal)s, %(costo_unitario)s)
    """,

    "d_ordenes_compra": """
        INSERT INTO d_ordenes_compra
            (id_orden_orig, id_proveedor, proveedor,
             fecha_emision, estado, total)
        VALUES
            (%(id_orden_orig)s, %(id_proveedor)s, %(proveedor)s,
             %(fecha_emision)s, %(estado)s, %(total)s)
    """,
}

TABLAS_ORDEN = [
    "d_inventario",
    "d_movimientos_inventario",
    "d_facturas",
    "d_facturas_detalle",
    "d_ordenes_compra",
]


# ---------------------------------------------------------------------------
# Lógica de importación
# ---------------------------------------------------------------------------

def importar_tabla(src_conn, dst_conn, tabla: str, batch_size: int) -> int:
    """
    Extrae todos los registros de src_conn e inserta en dst_conn.
    TRUNCATE previo garantiza idempotencia (se puede re-ejecutar sin duplicados).
    Retorna el número de filas insertadas.
    """
    print(f"  [{tabla}] extrayendo...", end=" ", flush=True)

    src_cur = src_conn.cursor(dictionary=True)
    src_cur.execute(SQL_EXTRACT[tabla])
    rows = src_cur.fetchall()
    src_cur.close()

    total = len(rows)
    print(f"{total} filas.")

    if total == 0:
        print(f"  [{tabla}] sin datos, se omite TRUNCATE.")
        return 0

    dst_cur = dst_conn.cursor()
    dst_cur.execute(f"SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute(f"TRUNCATE TABLE {tabla}")
    dst_cur.execute(f"SET FOREIGN_KEY_CHECKS = 1")

    insertados = 0
    for offset in range(0, total, batch_size):
        lote = rows[offset : offset + batch_size]
        dst_cur.executemany(SQL_INSERT[tabla], lote)
        insertados += len(lote)
        pct = insertados * 100 // total
        print(f"\r  [{tabla}] insertando... {insertados}/{total} ({pct}%)", end="", flush=True)

    dst_conn.commit()
    dst_cur.close()
    print(f"\r  [{tabla}] {insertados} filas insertadas.            ")
    return insertados


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa datos de comercial_db a comercial_desn_db aplicando desnormalización."
    )
    parser.add_argument(
        "--tabla",
        choices=TABLAS_ORDEN,
        metavar="TABLA",
        help=f"Importar solo esta tabla. Opciones: {', '.join(TABLAS_ORDEN)}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        metavar="N",
        help="Filas por lote de INSERT (default: 500)",
    )
    args = parser.parse_args()

    tablas = [args.tabla] if args.tabla else TABLAS_ORDEN

    print("=== Importación BD desnormalizada ===")
    print(f"Origen  : {os.getenv('DB_NAME')}")
    print(f"Destino : {os.getenv('DB_DESN_NAME')}")
    print(f"Tablas  : {', '.join(tablas)}")
    print(f"Lote    : {args.batch_size} filas")
    print()

    src = _conn()
    dst = _conn("DESN")

    total_filas = 0
    errores = []

    for tabla in tablas:
        try:
            total_filas += importar_tabla(src, dst, tabla, args.batch_size)
        except mysql.connector.Error as exc:
            dst.rollback()
            errores.append((tabla, str(exc)))
            print(f"  [{tabla}] ERROR: {exc}", file=sys.stderr)

    src.close()
    dst.close()

    print()
    if errores:
        print(f"Importación con errores en {len(errores)} tabla(s):")
        for t, msg in errores:
            print(f"  - {t}: {msg}")
        sys.exit(1)
    else:
        print(f"Importación completa: {total_filas} fila(s) en {len(tablas)} tabla(s).")


if __name__ == "__main__":
    main()
