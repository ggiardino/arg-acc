"""Pipeline DDJJ — Declaraciones Juradas Patrimoniales Integrales.

Fuente: Portal de Datos de la Justicia Argentina (datos.jus.gob.ar),
dataset `declaraciones-juradas-patrimoniales-integrales`. Son las
declaraciones de carácter público presentadas bajo la Ley 25.188 de
Ética en el Ejercicio de la Función Pública (mod. Ley 26.857).

El dataset trae, por año fiscal, hasta cuatro archivos CSV:

  declaraciones-juradas-AAAA-consolidado-al-*.csv         (declaración)
  declaraciones-juradas-bienes-AAAA-consolidado-al-*.csv  (bienes)
  declaraciones-juradas-deudas-AAAA-consolidado-al-*.csv  (deudas)
  declaraciones-juradas-grupo-familiar-AAAA-*.csv         (grupo familiar)

Subgrafo construido:

  (Persona)-[:PRESENTO]->(DeclaracionJurada)
  (DeclaracionJurada)-[:DECLARA]->(BienDeclarado)
  (DeclaracionJurada)-[:REGISTRA_DEUDA]->(Deuda)
  (DeclaracionJurada)-[:CARGO_DECLARADO_EN]->(Organismo)
  (Persona)-[:FAMILIAR_DE {vinculo}]->(Persona)        // grupo familiar
  (DeclaracionJurada)-[:SEGUN_FUENTE]->(FuenteDocumento)
  (DeclaracionJurada)-[:INGESTADO_EN]->(CorridaIngesta)

Alimenta la regla de enriquecimiento patrimonial: la variación
interanual de `patrimonio_total` se cruza con contratos públicos.

Privacidad (Ley 25.326): el núcleo del CUIL coincidente con el DNI no se
publica; el grafo expone `cuil_parcial`. El grupo familiar son personas
no funcionarias: solo se incorporan por su vínculo con un dato público y
siempre enmascaradas.

Idempotente: claves naturales (`dj_id`, CUIL) + `MERGE`; los ids de
bienes/deudas son hashes deterministas de su contenido.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import sys
from pathlib import Path

from aracc_etl.base import Pipeline
from aracc_etl.download import descargar, listar_recursos_ckan
from aracc_etl.transforms.identificadores import cuit_enmascarado, normalizar_cuit
from aracc_etl.transforms.montos import normalizar_monto

logger = logging.getLogger(__name__)

PORTAL = "https://datos.jus.gob.ar"
DATASET_ID = "declaraciones-juradas-patrimoniales-integrales"

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

_LOAD_DECLARACIONES = """
UNWIND $rows AS row
MERGE (p:Persona {cuil: row.cuil})
  ON CREATE SET p.nombre = row.nombre
  SET p.cuil_parcial = row.cuil_parcial,
      p.nombre = coalesce(p.nombre, row.nombre)
MERGE (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
  SET d.anio              = row.anio,
      d.tipo              = row.tipo,
      d.rectificativa     = row.rectificativa,
      d.cargo             = row.cargo,
      d.sector            = row.sector,
      d.desde             = row.desde,
      d.proveedor_contratista = row.proveedor_contratista,
      d.total_bienes      = row.total_bienes,
      d.total_deudas      = row.total_deudas,
      d.patrimonio_total  = row.total_bienes,
      d.patrimonio_neto   = row.patrimonio_neto
MERGE (p)-[:PRESENTO]->(d)
FOREACH (_ IN CASE WHEN row.organismo_id IS NULL THEN [] ELSE [1] END |
  MERGE (o:Organismo {organismo_id: row.organismo_id})
    ON CREATE SET o.nombre = row.organismo, o.nivel = 'nacional'
  MERGE (d)-[:CARGO_DECLARADO_EN]->(o)
)
MERGE (doc:FuenteDocumento {doc_id: row.doc_id})
  SET doc.source_id = 'ddjj', doc.url = row.url,
      doc.fecha_captura = row.fecha_captura
MERGE (d)-[:SEGUN_FUENTE]->(doc)
MERGE (run:CorridaIngesta {corrida_id: row.corrida_id})
MERGE (d)-[:INGESTADO_EN]->(run)
"""

_LOAD_BIENES = """
UNWIND $rows AS row
MATCH (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
MERGE (b:BienDeclarado {bien_id: row.bien_id})
  SET b.tipo          = row.tipo,
      b.descripcion   = row.descripcion,
      b.valor         = row.valor,
      b.origen_fondos = row.origen_fondos,
      b.titularidad   = row.titularidad,
      b.periodo       = row.periodo
MERGE (d)-[:DECLARA]->(b)
"""

_LOAD_DEUDAS = """
UNWIND $rows AS row
MATCH (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
MERGE (deuda:Deuda {deuda_id: row.deuda_id})
  SET deuda.tipo          = row.tipo,
      deuda.descripcion   = row.descripcion,
      deuda.clasificacion = row.clasificacion,
      deuda.radicacion    = row.radicacion,
      deuda.importe       = row.importe,
      deuda.periodo       = row.periodo
MERGE (d)-[:REGISTRA_DEUDA]->(deuda)
"""

_LOAD_FAMILIARES = """
UNWIND $rows AS row
MATCH (titular:Persona {cuil: row.cuil_titular})
MERGE (fam:Persona {cuil: row.cuil_familiar})
  ON CREATE SET fam.nombre = row.nombre_familiar
  SET fam.cuil_parcial = row.cuil_familiar_parcial
MERGE (titular)-[r:FAMILIAR_DE]->(fam)
  SET r.vinculo = row.vinculo
"""


def _slug(texto: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in texto.lower()).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base[:80]


def _hash_id(prefijo: str, *partes: object) -> str:
    crudo = "|".join(str(p) for p in partes)
    return f"{prefijo}-{hashlib.md5(crudo.encode('utf-8')).hexdigest()[:16]}"


def _clasificar_archivo(nombre: str) -> str | None:
    """Mapea un nombre de archivo/recurso a su tipo lógico."""
    n = nombre.lower()
    if "bienes" in n:
        return "bienes"
    if "deuda" in n:
        return "deudas"
    if "familiar" in n:
        return "familiares"
    if "consolidado" in n or "declaraciones-juradas" in n:
        return "declaraciones"
    return None


def _int(valor: object) -> int | None:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


class DeclaracionesJuradasPipeline(Pipeline):
    """Ingesta de DDJJ Patrimoniales Integrales de datos.jus.gob.ar."""

    name = "DDJJ Patrimoniales (datos.jus.gob.ar)"
    source_id = "ddjj"

    def __init__(
        self,
        *args,
        anio: int | None = None,
        offline: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if anio is None:
            raise ValueError("El pipeline ddjj requiere --anio (año fiscal).")
        self.anio = int(anio)
        # offline: no intentar descargar; usar solo archivos ya presentes.
        self.offline = offline
        self._archivos: dict[str, Path] = {}

    # ── extract ─────────────────────────────────────────────
    def extract(self) -> None:
        raw = Path(self.data_dir) / "ddjj" / "raw"
        raw.mkdir(parents=True, exist_ok=True)

        # 1) Archivos locales que coincidan con el año.
        for archivo in sorted(raw.glob(f"*{self.anio}*.csv")):
            tipo = _clasificar_archivo(archivo.name)
            if tipo:
                self._archivos.setdefault(tipo, archivo)

        # 2) Si falta el archivo principal y hay red, resolver vía CKAN.
        if "declaraciones" not in self._archivos and not self.offline:
            self._descargar_desde_ckan(raw)

        if "declaraciones" not in self._archivos:
            raise FileNotFoundError(
                f"No se encontró el archivo principal de DDJJ {self.anio}. "
                f"Descargá los CSV del dataset '{DATASET_ID}' de {PORTAL} "
                f"a {raw}/, o ejecutá con conectividad."
            )
        logger.info(
            "[%s] archivos: %s",
            self.name,
            {k: v.name for k, v in self._archivos.items()},
        )

    def _descargar_desde_ckan(self, raw: Path) -> None:
        logger.info("[%s] resolviendo recursos CKAN para %s", self.name, self.anio)
        recursos = listar_recursos_ckan(PORTAL, DATASET_ID)
        for recurso in recursos:
            nombre = recurso.get("name", "") or ""
            url = recurso.get("url", "") or ""
            if not url or str(self.anio) not in (nombre + url):
                continue
            tipo = _clasificar_archivo(nombre) or _clasificar_archivo(url)
            if not tipo or tipo in self._archivos:
                continue
            destino = raw / f"ddjj-{tipo}-{self.anio}.csv"
            try:
                descargar(url, destino)
                self._archivos[tipo] = destino
            except RuntimeError as exc:
                logger.warning("no se pudo descargar %s: %s", tipo, exc)

    # ── transform ───────────────────────────────────────────
    def transform(self) -> None:
        self._declaraciones = self._transform_declaraciones()
        self._bienes = self._transform_detalle("bienes", self._fila_bien)
        self._deudas = self._transform_detalle("deudas", self._fila_deuda)
        self._familiares = self._transform_familiares()

    def _leer_csv(self, tipo: str):
        archivo = self._archivos.get(tipo)
        if not archivo:
            return
        with archivo.open(encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)

    def _transform_declaraciones(self) -> list[dict]:
        filas: list[dict] = []
        for raw in self._leer_csv("declaraciones"):
            self.rows_in += 1
            if self.limit and self.rows_in > self.limit:
                break
            cuil = normalizar_cuit(raw.get("cuit"))
            dj_id = (raw.get("dj_id") or "").strip()
            if not cuil or not dj_id:
                continue  # sin funcionario identificable o sin id: se descarta
            total_bienes = normalizar_monto(raw.get("total_bienes_final"))
            total_deudas = normalizar_monto(raw.get("total_deudas_final"))
            patrimonio_neto = None
            if total_bienes is not None:
                patrimonio_neto = total_bienes - (total_deudas or 0.0)
            organismo = (raw.get("organismo") or "").strip()
            anio_raw = (raw.get("anio") or "").strip()
            filas.append(
                {
                    "ddjj_id": f"ddjj-{dj_id}",
                    "cuil": cuil,
                    "cuil_parcial": cuit_enmascarado(cuil),
                    "nombre": (raw.get("funcionario_apellido_nombre") or "").strip(),
                    "anio": int(anio_raw) if anio_raw.isdigit() else self.anio,
                    "tipo": (raw.get("tipo_declaracion_jurada_descripcion") or "").strip(),
                    "rectificativa": _int(raw.get("rectificativa")),
                    "cargo": (raw.get("cargo") or "").strip(),
                    "sector": (raw.get("sector") or "").strip(),
                    "desde": (raw.get("desde") or "").strip(),
                    "proveedor_contratista":
                        (raw.get("proveedor_contratista") or "").strip().upper() == "SI",
                    "organismo": organismo,
                    "organismo_id": f"org-{_slug(organismo)}" if organismo else None,
                    "total_bienes": total_bienes,
                    "total_deudas": total_deudas,
                    "patrimonio_neto": patrimonio_neto,
                    "doc_id": f"ddjj-doc-{dj_id}",
                    "url": f"{PORTAL}/dataset/{DATASET_ID}",
                    "fecha_captura": self.corrida_id.split("_")[-1],
                    "corrida_id": self.corrida_id,
                }
            )
        return filas

    def _transform_detalle(self, tipo: str, fila_fn) -> list[dict]:
        filas: list[dict] = []
        for raw in self._leer_csv(tipo):
            dj_id = (raw.get("dj_id") or "").strip()
            if not dj_id:
                continue
            fila = fila_fn(raw, dj_id)
            if fila:
                filas.append(fila)
        return filas

    @staticmethod
    def _periodo(raw: dict) -> str:
        codigo = (raw.get("periodo_inicio_cierre") or "").strip().upper()
        return {"I": "inicio", "C": "cierre"}.get(codigo, codigo or "n/d")

    def _fila_bien(self, raw: dict, dj_id: str) -> dict:
        periodo = self._periodo(raw)
        descripcion = (raw.get("bien_descripcion") or "").strip()
        tipo = (raw.get("bien_tipo") or "").strip()
        valor = normalizar_monto(raw.get("bien_importe"))
        return {
            "ddjj_id": f"ddjj-{dj_id}",
            "bien_id": _hash_id("bien", dj_id, periodo, tipo, descripcion, valor),
            "tipo": tipo,
            "descripcion": descripcion,
            "valor": valor,
            "origen_fondos": (raw.get("bien_origen_fondos") or "").strip(),
            "titularidad": (raw.get("bien_titularidad") or "").strip(),
            "periodo": periodo,
        }

    def _fila_deuda(self, raw: dict, dj_id: str) -> dict:
        periodo = self._periodo(raw)
        descripcion = (raw.get("deuda_descripcion") or "").strip()
        tipo = (raw.get("deuda_tipo") or "").strip()
        importe = normalizar_monto(raw.get("deuda_importe"))
        return {
            "ddjj_id": f"ddjj-{dj_id}",
            "deuda_id": _hash_id("deuda", dj_id, periodo, tipo, descripcion, importe),
            "tipo": tipo,
            "descripcion": descripcion,
            "clasificacion": (raw.get("deuda_clasificacion") or "").strip(),
            "radicacion": (raw.get("deuda_radicacion_localizacion") or "").strip(),
            "importe": importe,
            "periodo": periodo,
        }

    def _transform_familiares(self) -> list[dict]:
        filas: list[dict] = []
        for raw in self._leer_csv("familiares"):
            cuil_titular = normalizar_cuit(raw.get("cuit"))
            cuil_familiar = normalizar_cuit(raw.get("familiar_cuit"))
            # Sin CUIL del familiar no hay clave estable: se omite el vínculo.
            if not cuil_titular or not cuil_familiar:
                continue
            filas.append(
                {
                    "cuil_titular": cuil_titular,
                    "cuil_familiar": cuil_familiar,
                    "cuil_familiar_parcial": cuit_enmascarado(cuil_familiar),
                    "nombre_familiar": (raw.get("familiar_apellido_nombre") or "").strip(),
                    "vinculo": (raw.get("familiar_parentesco") or "").strip(),
                }
            )
        return filas

    # ── load ────────────────────────────────────────────────
    def load(self) -> None:
        with self.driver.session(database=self.neo4j_database) as session:
            self._cargar(session, _LOAD_DECLARACIONES, self._declaraciones)
            self.rows_loaded = len(self._declaraciones)
            self._cargar(session, _LOAD_BIENES, self._bienes)
            self._cargar(session, _LOAD_DEUDAS, self._deudas)
            self._cargar(session, _LOAD_FAMILIARES, self._familiares)
        logger.info(
            "[%s] cargados: %d DDJJ, %d bienes, %d deudas, %d familiares",
            self.name, len(self._declaraciones), len(self._bienes),
            len(self._deudas), len(self._familiares),
        )

    def _cargar(self, session, query: str, filas: list[dict]) -> None:
        for i in range(0, len(filas), self.chunk_size):
            session.run(query, rows=filas[i : i + self.chunk_size])
