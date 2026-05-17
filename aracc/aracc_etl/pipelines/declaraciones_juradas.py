"""Pipeline DDJJ patrimoniales — Oficina Anticorrupción.

Construye el subgrafo patrimonial de funcionarios:

    (Persona)-[:PRESENTO]->(DeclaracionJurada {anio, patrimonio_total})
    (DeclaracionJurada)-[:DECLARA]->(BienDeclarado {tipo, valor})
    (DeclaracionJurada)-[:SEGUN_FUENTE]->(FuenteDocumento)

Estos datos alimentan la regla de detección de enriquecimiento
patrimonial (variación interanual del patrimonio total vs. contratos
ganados por empresas vinculadas).

Privacidad: las DDJJ contienen datos sensibles. El núcleo del CUIL se
almacena solo en el atributo `cuil` (visible únicamente en despliegues
internos autenticados); el grafo público expone `cuil_parcial`.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from aracc_etl.base import Pipeline
from aracc_etl.transforms.identificadores import cuit_enmascarado, normalizar_cuit
from aracc_etl.transforms.montos import normalizar_monto

logger = logging.getLogger(__name__)

_LOAD_DDJJ = """
UNWIND $rows AS row
MERGE (p:Persona {cuil: row.cuil})
  ON CREATE SET p.nombre = row.nombre,
                p.cuil_parcial = row.cuil_parcial
MERGE (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
  SET d.anio = row.anio,
      d.fecha = row.fecha,
      d.patrimonio_total = row.patrimonio_total
MERGE (p)-[:PRESENTO]->(d)
MERGE (doc:FuenteDocumento {doc_id: row.doc_id})
  SET doc.source_id = 'ddjj_oa', doc.url = row.url,
      doc.fecha_captura = row.fecha_captura
MERGE (d)-[:SEGUN_FUENTE]->(doc)
WITH d, row
UNWIND row.bienes AS bien
MERGE (b:BienDeclarado {bien_id: bien.bien_id})
  SET b.tipo = bien.tipo, b.valor = bien.valor, b.descripcion = bien.descripcion
MERGE (d)-[:DECLARA]->(b)
"""


class DeclaracionesJuradasPipeline(Pipeline):
    name = "DDJJ Patrimoniales (OA)"
    source_id = "ddjj_oa"

    def extract(self) -> None:
        base = Path(self.data_dir) / "ddjj_oa" / "raw"
        self._ddjj_csv = base / "declaraciones.csv"
        self._bienes_csv = base / "bienes.csv"
        for path in (self._ddjj_csv, self._bienes_csv):
            if not path.exists():
                raise FileNotFoundError(f"No se encontró {path}")

    def transform(self) -> None:
        # Agrupa los bienes por declaración para cargarlos anidados.
        bienes_por_ddjj: dict[str, list[dict]] = {}
        with self._bienes_csv.open(encoding="utf-8-sig") as fh:
            for raw in csv.DictReader(fh):
                ddjj_id = raw.get("ddjj_id", "")
                bienes_por_ddjj.setdefault(ddjj_id, []).append(
                    {
                        "bien_id": f"bien-{raw['bien_id']}",
                        "tipo": (raw.get("tipo") or "").strip().upper(),
                        "valor": normalizar_monto(raw.get("valor")),
                        "descripcion": (raw.get("descripcion") or "").strip(),
                    }
                )

        self._rows: list[dict] = []
        with self._ddjj_csv.open(encoding="utf-8-sig") as fh:
            for raw in csv.DictReader(fh):
                self.rows_in += 1
                if self.limit and self.rows_in > self.limit:
                    break
                cuil = normalizar_cuit(raw.get("cuil"))
                ddjj_id = raw.get("ddjj_id", "")
                if not cuil or not ddjj_id:
                    continue
                self._rows.append(
                    {
                        "cuil": cuil,
                        "cuil_parcial": cuit_enmascarado(cuil),
                        "nombre": (raw.get("nombre") or "").strip(),
                        "ddjj_id": f"ddjj-{ddjj_id}",
                        "anio": int(raw["anio"]) if raw.get("anio") else None,
                        "fecha": raw.get("fecha", ""),
                        "patrimonio_total": normalizar_monto(raw.get("patrimonio_total")),
                        "bienes": bienes_por_ddjj.get(ddjj_id, []),
                        "doc_id": f"ddjj-doc-{ddjj_id}",
                        "url": raw.get("url_fuente", ""),
                        "fecha_captura": raw.get("fecha_captura", ""),
                    }
                )

    def load(self) -> None:
        with self.driver.session(database=self.neo4j_database) as session:
            for i in range(0, len(self._rows), self.chunk_size):
                chunk = self._rows[i : i + self.chunk_size]
                session.run(_LOAD_DDJJ, rows=chunk)
                self.rows_loaded += len(chunk)
