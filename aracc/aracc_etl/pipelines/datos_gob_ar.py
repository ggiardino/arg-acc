"""Pipeline datos.gob.ar — descubrimiento de datasets vía API CKAN.

El Portal Nacional de Datos Abiertos expone una API CKAN estándar. Este
pipeline no carga un dataset concreto: indexa el catálogo y registra
cada recurso disponible como :FuenteDocumento, de modo que el resto de
los pipelines puedan resolver URLs de descarga de forma reproducible.
"""

from __future__ import annotations

import logging

import httpx

from aracc_etl.base import Pipeline

logger = logging.getLogger(__name__)

_CKAN_BASE = "https://datos.gob.ar/api/3/action"

_LOAD_CATALOGO = """
UNWIND $rows AS row
MERGE (doc:FuenteDocumento {doc_id: row.doc_id})
  SET doc.source_id = 'datos_gob_ar',
      doc.titulo = row.titulo,
      doc.url = row.url,
      doc.formato = row.formato,
      doc.fecha_publicacion = row.fecha_publicacion,
      doc.fecha_captura = row.fecha_captura
"""


class DatosGobArPipeline(Pipeline):
    name = "datos.gob.ar (catálogo CKAN)"
    source_id = "datos_gob_ar"

    def __init__(self, *args, consulta: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # `consulta`: filtra el catálogo (ej. 'contrataciones', 'electoral').
        self.consulta = consulta

    def extract(self) -> None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{_CKAN_BASE}/package_search",
                params={"q": self.consulta, "rows": self.limit or 200},
            )
            resp.raise_for_status()
            self._datasets = resp.json()["result"]["results"]

    def transform(self) -> None:
        from datetime import UTC, datetime

        ahora = datetime.now(tz=UTC).isoformat()
        self._rows: list[dict] = []
        for ds in self._datasets:
            self.rows_in += 1
            for recurso in ds.get("resources", []):
                self._rows.append(
                    {
                        "doc_id": f"datosgobar-{recurso['id']}",
                        "titulo": ds.get("title", ""),
                        "url": recurso.get("url", ""),
                        "formato": (recurso.get("format") or "").upper(),
                        "fecha_publicacion": recurso.get("created", ""),
                        "fecha_captura": ahora,
                    }
                )

    def load(self) -> None:
        with self.driver.session(database=self.neo4j_database) as session:
            for i in range(0, len(self._rows), self.chunk_size):
                chunk = self._rows[i : i + self.chunk_size]
                session.run(_LOAD_CATALOGO, rows=chunk)
                self.rows_loaded += len(chunk)
