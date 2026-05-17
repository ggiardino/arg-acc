"""Flujos Prefect para la ejecución programada e idempotente de los ETL.

Cada pipeline es una task; los deployments definen la cadencia según
`sources.yml` (ej. BORA diario, COMPR.AR mensual). Prefect aporta
reintentos, observabilidad y backfills sin código adicional.

Despliegue local:
    prefect server start
    python -m aracc_etl.flows   # registra los deployments
"""

from __future__ import annotations

import os

from prefect import flow, task
from prefect.schedules import Cron

from aracc_etl.runner import PIPELINES, _driver


@task(retries=3, retry_delay_seconds=[60, 300, 900])
def ejecutar_pipeline(source_id: str, limit: int | None = None) -> dict:
    """Ejecuta un pipeline y devuelve métricas de la corrida."""
    with _driver() as driver:
        pipeline = PIPELINES[source_id](
            driver=driver,
            data_dir=os.getenv("DATA_DIR", "./data"),
            limit=limit,
        )
        pipeline.run()
        return {"source_id": source_id, "rows_loaded": pipeline.rows_loaded}


@flow(name="ar-acc-ingesta-diaria")
def ingesta_diaria() -> None:
    """Fuentes de alta frecuencia (Boletín Oficial, padrón AFIP)."""
    for source_id in ("datos_gob_ar",):
        ejecutar_pipeline(source_id)


@flow(name="ar-acc-ingesta-mensual")
def ingesta_mensual() -> None:
    """Fuentes de cadencia mensual (compras, presupuesto)."""
    for source_id in ("comprar",):
        ejecutar_pipeline(source_id)


if __name__ == "__main__":
    ingesta_diaria.serve(name="diaria", schedule=Cron("0 6 * * *"))
    ingesta_mensual.serve(name="mensual", schedule=Cron("0 7 1 * *"))
