#!/usr/bin/env python
"""
ETL: comercial_desn_db → comercial_resumen_db

Uso:
    python run_etl.py
    python run_etl.py --tabla r_facturas
    python run_etl.py --tabla r_facturas --tabla r_ordenes_compra
    python run_etl.py --dry-run
    python run_etl.py --workers 2

Tablas disponibles:
    r_inventario              full reload      (snapshot de stock)
    r_movimientos_inventario  incremental      (append-only, watermark)
    r_facturas                upsert           (estado/saldo mutables)
    r_facturas_detalle        incremental      (líneas inmutables)
    r_ordenes_compra          upsert           (estado mutable)
"""
import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from etl.pipeline import ejecutar, TABLAS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL comercial_desn_db → comercial_resumen_db",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tabla",
        dest="tablas",
        action="append",
        choices=list(TABLAS.keys()),
        metavar="TABLA",
        help=(
            "Procesar solo esta tabla (repetible: --tabla A --tabla B). "
            f"Opciones: {', '.join(TABLAS)}"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin escribir en la BD destino",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Número de tablas a procesar en paralelo (default: 4)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de logging (default: INFO)",
    )
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    ok = ejecutar(
        tablas=args.tablas,
        dry_run=args.dry_run,
        max_workers=args.workers,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
