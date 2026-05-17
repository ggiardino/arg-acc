"""CLI de ejecución de pipelines ETL de ar-acc.

Uso:
    aracc-etl run <source_id> [--limit N] [--since YYYY-MM-DD]
    aracc-etl list

El mapa de pipelines se mantiene en sincronía con `sources.yml`.
"""

from __future__ import annotations

import argparse
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
    "ddjj_oa": DeclaracionesJuradasPipeline,
}


def _driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aracc-etl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Ejecutar un pipeline")
    run.add_argument("source_id", choices=sorted(PIPELINES))
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--since", default=None, help="Ingesta incremental desde YYYY-MM-DD")
    run.add_argument("--data-dir", default=os.getenv("DATA_DIR", "./data"))

    sub.add_parser("list", help="Listar pipelines disponibles")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        for sid in sorted(PIPELINES):
            print(sid)
        return 0

    pipeline_cls = PIPELINES[args.source_id]
    with _driver() as driver:
        pipeline = pipeline_cls(
            driver=driver,
            data_dir=args.data_dir,
            limit=args.limit,
            since=args.since,
        )
        pipeline.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
