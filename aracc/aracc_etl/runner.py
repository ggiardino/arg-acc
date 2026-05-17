"""CLI de ejecución de pipelines ETL de ar-acc.

Uso:
    aracc-etl run <source_id> [--limit N] [--since YYYY-MM-DD]
                              [--anio AAAA] [--offline]
    aracc-etl list

Cada pipeline declara sus propios parámetros en su `__init__`; el runner
sólo le pasa los que esa firma acepta, de modo que agregar un pipeline
con opciones nuevas no rompe a los demás.
"""

from __future__ import annotations

import argparse
import inspect
import logging
import os
import sys

from neo4j import GraphDatabase

from aracc_etl.pipelines.comprar import ComprarPipeline
from aracc_etl.pipelines.datos_gob_ar import DatosGobArPipeline
from aracc_etl.pipelines.declaraciones_juradas import DeclaracionesJuradasPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Registro de pipelines disponibles. Crece con cada contribución.
PIPELINES = {
    "datos_gob_ar": DatosGobArPipeline,
    "comprar": ComprarPipeline,
    "ddjj": DeclaracionesJuradasPipeline,
}


def _driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )


def _kwargs_para(pipeline_cls, candidatos: dict) -> dict:
    """Filtra `candidatos` a los parámetros que acepta el __init__."""
    firma = inspect.signature(pipeline_cls.__init__)
    return {
        k: v for k, v in candidatos.items()
        if k in firma.parameters and v is not None
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aracc-etl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ejecutar un pipeline")
    run.add_argument("source_id", choices=sorted(PIPELINES))
    run.add_argument("--limit", type=int, default=None,
                     help="Máximo de registros a procesar")
    run.add_argument("--since", default=None,
                     help="Ingesta incremental desde YYYY-MM-DD")
    run.add_argument("--anio", type=int, default=None,
                     help="Año fiscal (requerido por el pipeline ddjj)")
    run.add_argument("--offline", action="store_true",
                     help="No descargar; usar solo archivos locales")
    run.add_argument("--data-dir", default=os.getenv("DATA_DIR", "./data"))

    sub.add_parser("list", help="Listar pipelines disponibles")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        for sid in sorted(PIPELINES):
            print(sid)
        return 0

    pipeline_cls = PIPELINES[args.source_id]
    candidatos = {
        "data_dir": args.data_dir,
        "limit": args.limit,
        "since": args.since,
        "anio": args.anio,
        "offline": args.offline or None,
    }
    with _driver() as driver:
        pipeline = pipeline_cls(driver=driver, **_kwargs_para(pipeline_cls, candidatos))
        pipeline.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
