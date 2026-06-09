"""
Importación de datos desde comercial_desn_db → comercial_resumen_db.

Para cada tabla r_* hace TRUNCATE + INSERT en lotes (re-importación limpia).
Las queries de extracción leen directamente de las tablas d_* sin JOINs
adicionales, ya que la desnormalizada tiene todos los campos embebidos.

Uso:
    python db/importar_resumen.py
    python db/importar_resumen.py --tabla r_inventario
    python db/importar_resumen.py --batch-size 1000
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
    sep = f"_{prefix}" if prefix else ""
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
# Queries de extracción — full-scan de d_*, sin filtros de parámetro.
# Solo se excluyen registros con deleted_at IS NOT NULL (soft-deleted).
# Los filtros de negocio (estado, saldo, etc.) quedan en las queries de reporte.
# ---------------------------------------------------------------------------

SQL_EXTRACT: dict[str, str] = {

    # Copia exacta de d_inventario excluyendo soft-deleted
    "r_inventario": """
        SELECT
            id_producto,
            codigo_producto,
            nombre_producto,
            id_presentacion,
            presentacion,
            id_bodega,
            bodega,
            stock_actual,
            stock_minimo,
            stock_maximo
        FROM d_inventario
        WHERE deleted_at IS NULL
        ORDER BY nombre_producto, presentacion
    """,

    # Copia exacta de d_movimientos_inventario excluyendo soft-deleted
    "r_movimientos_inventario": """
        SELECT
            id                 AS id_movimiento_orig,
            id_producto,
            codigo_producto,
            nombre_producto,
            id_bodega,
            bodega,
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
        ORDER BY fecha ASC
    """,

    # Copia exacta de d_facturas excluyendo soft-deleted
    "r_facturas": """
        SELECT
            id                 AS id_factura_orig,
            numero_factura,
            fecha_emision,
            fecha_vencimiento,
            id_sucursal,
            sucursal,
            id_cliente,
            cliente,
            subtotal,
            descuento,
            impuesto,
            total,
            saldo,
            estado
        FROM d_facturas
        WHERE deleted_at IS NULL
        ORDER BY fecha_emision, numero_factura
    """,

    # Copia exacta de d_facturas_detalle excluyendo soft-deleted
    "r_facturas_detalle": """
        SELECT
            id                 AS id_detalle_orig,
            id_factura,
            numero_factura,
            fecha_emision,
            id_sucursal,
            estado_factura,
            id_producto,
            codigo_producto,
            nombre_producto,
            id_categoria,
            categoria,
            cantidad,
            subtotal,
            costo_unitario
        FROM d_facturas_detalle
        WHERE deleted_at IS NULL
        ORDER BY fecha_emision, id_factura, id
    """,

    # Copia exacta de d_ordenes_compra excluyendo soft-deleted
    "r_ordenes_compra": """
        SELECT
            id                 AS id_orden_orig,
            id_proveedor,
            proveedor,
            fecha_emision,
            estado,
            total
        FROM d_ordenes_compra
        WHERE deleted_at IS NULL
        ORDER BY fecha_emision
    """,
}


# ---------------------------------------------------------------------------
# INSERT statements — columnas en el mismo orden que los SELECT de arriba
# ---------------------------------------------------------------------------

SQL_INSERT: dict[str, str] = {

    "r_inventario": """
        INSERT INTO r_inventario
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

    "r_movimientos_inventario": """
        INSERT INTO r_movimientos_inventario
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

    "r_facturas": """
        INSERT INTO r_facturas
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

    "r_facturas_detalle": """
        INSERT INTO r_facturas_detalle
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

    "r_ordenes_compra": """
        INSERT INTO r_ordenes_compra
            (id_orden_orig, id_proveedor, proveedor,
             fecha_emision, estado, total)
        VALUES
            (%(id_orden_orig)s, %(id_proveedor)s, %(proveedor)s,
             %(fecha_emision)s, %(estado)s, %(total)s)
    """,
}

TABLAS_ORDEN = [
    "r_inventario",
    "r_movimientos_inventario",
    "r_facturas",
    "r_facturas_detalle",
    "r_ordenes_compra",
]


# ---------------------------------------------------------------------------
# Lógica de importación
# ---------------------------------------------------------------------------

def importar_tabla(src_conn, dst_conn, tabla: str, batch_size: int) -> int:
    """
    Extrae todos los registros de src_conn (d_*) e inserta en dst_conn (r_*).
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
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    dst_cur.execute(f"TRUNCATE TABLE {tabla}")
    dst_cur.execute("SET FOREIGN_KEY_CHECKS = 1")

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
        description="Importa datos de comercial_desn_db a comercial_resumen_db."
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

    print("=== Importación BD resumen ===")
    print(f"Origen  : {os.getenv('DB_DESN_NAME')}")
    print(f"Destino : {os.getenv('DB_RESUMEN_NAME')}")
    print(f"Tablas  : {', '.join(tablas)}")
    print(f"Lote    : {args.batch_size} filas")
    print()

    src = _conn("DESN")
    dst = _conn("RESUMEN")

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
