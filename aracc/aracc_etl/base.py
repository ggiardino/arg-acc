"""Clase base para los pipelines ETL de ar-acc.

Cada pipeline implementa extract/transform/load. `run()` registra cada
ejecución como un nodo :CorridaIngesta en el grafo, lo que da
idempotencia auditable: re-ejecutar un pipeline no duplica datos y deja
rastro de cuándo y con qué resultado se ingirió cada fuente.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from neo4j import Driver

logger = logging.getLogger(__name__)


class Pipeline(ABC):
    """Base de todos los pipelines de ingesta."""

    name: str
    source_id: str

    def __init__(
        self,
        driver: Driver,
        data_dir: str = "./data",
        limit: int | None = None,
        chunk_size: int = 50_000,
        neo4j_database: str | None = None,
        since: str | None = None,
    ) -> None:
        self.driver = driver
        self.data_dir = data_dir
        self.limit = limit
        self.chunk_size = chunk_size
        self.neo4j_database = neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")
        # `since`: ingesta incremental (solo registros posteriores a esta fecha).
        self.since = since
        self.rows_in: int = 0
        self.rows_loaded: int = 0
        key = getattr(self, "source_id", getattr(self, "name", "fuente_desconocida"))
        self.corrida_id = f"{key}_{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"

    @abstractmethod
    def extract(self) -> None:
        """Descargar los datos crudos de la fuente oficial."""

    @abstractmethod
    def transform(self) -> None:
        """Normalizar, deduplicar y validar contra el contrato de datos."""

    @abstractmethod
    def load(self) -> None:
        """Cargar al grafo Neo4j con MERGE idempotente."""

    def run(self) -> None:
        """Ejecuta el pipeline completo y registra la corrida."""
        started = datetime.now(tz=UTC).isoformat()
        self._registrar_corrida(estado="ejecutando", inicio=started)
        try:
            logger.info("[%s] extracción...", self.name)
            self.extract()
            logger.info("[%s] transformación...", self.name)
            self.transform()
            logger.info("[%s] carga...", self.name)
            self.load()
            self._registrar_corrida(
                estado="loaded",
                inicio=started,
                fin=datetime.now(tz=UTC).isoformat(),
            )
            logger.info(
                "[%s] completo: %d leídos, %d cargados.",
                self.name, self.rows_in, self.rows_loaded,
            )
        except Exception as exc:  # noqa: BLE001 - re-raise tras registrar
            self._registrar_corrida(
                estado="quality_fail",
                inicio=started,
                fin=datetime.now(tz=UTC).isoformat(),
                error=str(exc)[:1000],
            )
            raise

    def _registrar_corrida(
        self,
        *,
        estado: str,
        inicio: str,
        fin: str | None = None,
        error: str | None = None,
    ) -> None:
        query = """
        MERGE (c:CorridaIngesta {corrida_id: $corrida_id})
        SET c.source_id  = $source_id,
            c.estado     = $estado,
            c.inicio     = $inicio,
            c.fin        = $fin,
            c.rows_in    = $rows_in,
            c.rows_loaded = $rows_loaded,
            c.error      = $error
        """
        with self.driver.session(database=self.neo4j_database) as session:
            session.run(
                query,
                corrida_id=self.corrida_id,
                source_id=getattr(self, "source_id", self.name),
                estado=estado,
                inicio=inicio,
                fin=fin,
                rows_in=self.rows_in,
                rows_loaded=self.rows_loaded,
                error=error,
            )
