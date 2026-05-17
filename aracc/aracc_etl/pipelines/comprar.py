"""Pipeline COMPR.AR — compras y contrataciones públicas nacionales.

Construye el subgrafo de contratación:

    (Organismo)-[:CONVOCA]->(Licitacion)
    (Organismo)-[:CONTRATA]->(Contrato)
    (Contrato)-[:DERIVA_DE]->(Licitacion)
    (Empresa)-[:ADJUDICATARIA_DE {fecha}]->(Contrato)
    (Contrato)-[:SEGUN_FUENTE]->(FuenteDocumento)

Idempotente: las claves naturales (contrato_id, CUIT) + MERGE evitan
duplicados al re-ejecutar. Las relaciones de adjudicación llevan `fecha`
para habilitar las reglas de detección con solapamiento temporal.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from aracc_etl.base import Pipeline
from aracc_etl.transforms.identificadores import cuit_enmascarado, normalizar_cuit
from aracc_etl.transforms.montos import normalizar_monto

logger = logging.getLogger(__name__)

_LOAD_CONTRATOS = """
UNWIND $rows AS row
MERGE (o:Organismo {organismo_id: row.organismo_id})
  ON CREATE SET o.nombre = row.organismo_nombre,
                o.jurisdiccion = row.jurisdiccion,
                o.nivel = 'nacional'
MERGE (e:Empresa {cuit: row.cuit})
  ON CREATE SET e.razon_social = row.proveedor
MERGE (c:Contrato {contrato_id: row.contrato_id})
  SET c.objeto          = row.objeto,
      c.monto           = row.monto,
      c.precio_unitario = row.precio_unitario,
      c.modalidad       = row.modalidad,
      c.fecha           = row.fecha
MERGE (o)-[:CONTRATA]->(c)
MERGE (e)-[adj:ADJUDICATARIA_DE]->(c)
  SET adj.fecha = row.fecha
MERGE (doc:FuenteDocumento {doc_id: row.doc_id})
  SET doc.source_id = 'comprar', doc.url = row.url,
      doc.fecha_captura = row.fecha_captura
MERGE (c)-[:SEGUN_FUENTE]->(doc)
WITH c, row
MERGE (run:CorridaIngesta {corrida_id: row.corrida_id})
MERGE (c)-[:INGESTADO_EN]->(run)
"""


class ComprarPipeline(Pipeline):
    name = "COMPR.AR"
    source_id = "comprar"

    def extract(self) -> None:
        self._raw = Path(self.data_dir) / "comprar" / "raw" / "contratos.csv"
        if not self._raw.exists():
            raise FileNotFoundError(
                f"No se encontró {self._raw}. Ejecutá scripts/download_comprar.py"
            )

    def transform(self) -> None:
        self._rows: list[dict] = []
        with self._raw.open(encoding="utf-8-sig") as fh:
            for raw in csv.DictReader(fh):
                self.rows_in += 1
                if self.limit and self.rows_in > self.limit:
                    break
                cuit = normalizar_cuit(raw.get("cuit_proveedor"))
                if not cuit or not raw.get("numero_contrato"):
                    continue  # contrato sin proveedor identificable: se descarta
                if self.since and raw.get("fecha", "") < self.since:
                    continue
                self._rows.append(
                    {
                        "contrato_id": f"comprar-{raw['numero_contrato']}",
                        "objeto": (raw.get("objeto") or "").strip(),
                        "monto": normalizar_monto(raw.get("monto_total")),
                        "precio_unitario": normalizar_monto(raw.get("precio_unitario")),
                        "modalidad": (raw.get("modalidad") or "").strip().upper(),
                        "fecha": raw.get("fecha", ""),
                        "cuit": cuit,
                        "proveedor": (raw.get("razon_social") or "").strip(),
                        "organismo_id": raw.get("organismo_id", "").strip(),
                        "organismo_nombre": (raw.get("organismo") or "").strip(),
                        "jurisdiccion": (raw.get("jurisdiccion") or "").strip(),
                        "doc_id": f"comprar-doc-{raw['numero_contrato']}",
                        "url": raw.get("url_fuente", ""),
                        "fecha_captura": raw.get("fecha_captura", ""),
                        "corrida_id": self.corrida_id,
                        # Identificador parcial precalculado para el modo público.
                        "cuit_parcial": cuit_enmascarado(cuit),
                    }
                )

    def load(self) -> None:
        with self.driver.session(database=self.neo4j_database) as session:
            for i in range(0, len(self._rows), self.chunk_size):
                chunk = self._rows[i : i + self.chunk_size]
                session.run(_LOAD_CONTRATOS, rows=chunk)
                self.rows_loaded += len(chunk)
