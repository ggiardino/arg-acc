"""Cargador de datos REALES — Declaraciones Juradas Patrimoniales Integrales.

Fuente oficial: Portal de Datos de la Justicia Argentina
(https://datos.jus.gob.ar), dataset
`declaraciones-juradas-patrimoniales-integrales`. Son las declaraciones
de carácter público presentadas bajo la Ley 25.188 de Ética en el
Ejercicio de la Función Pública (mod. Ley 26.857).

Construye el subgrafo que consume el dashboard de inconsistencias:

  (Persona)-[:PRESENTO]->(DeclaracionJurada)
  (DeclaracionJurada)-[:DECLARA]->(BienDeclarado)
  (DeclaracionJurada)-[:REGISTRA_DEUDA]->(Deuda)
  (DeclaracionJurada)-[:CARGO_DECLARADO_EN]->(Organismo)
  (DeclaracionJurada)-[:SEGUN_FUENTE]->(FuenteDocumento)
  (Persona)-[:FAMILIAR_DE {vinculo}]->(Persona)

Uso:
    # Descarga automática del año (requiere salida a internet):
    python pipelines/import_ddjj_real.py --anio 2023

    # Modo offline: usá CSV ya descargados en data/ddjj/raw/
    python pipelines/import_ddjj_real.py --anio 2023 --offline

    # Borrar primero los datos de DDJJ ya cargados:
    python pipelines/import_ddjj_real.py --anio 2023 --limpiar

Si tu red bloquea el portal, descargá manualmente los CSV del dataset
desde la página oficial y dejalos en data/ddjj/raw/, luego usá --offline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import shutil
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from neo4j import GraphDatabase  # noqa: E402

from config.settings import settings  # noqa: E402

PORTAL = "https://datos.jus.gob.ar"
DATASET_ID = "declaraciones-juradas-patrimoniales-integrales"
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "ddjj" / "raw"

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# --------------------------------------------------------------------------
# Normalización (formato argentino)
# --------------------------------------------------------------------------

_LIMPIEZA_MONTO = re.compile(r"[^\d,.\-]")
_SOLO_DIGITOS = re.compile(r"\D+")
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar_monto(valor) -> float | None:
    """'1.234.567,89' -> 1234567.89. Devuelve None si no es válido."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = _LIMPIEZA_MONTO.sub("", str(valor)).strip()
    if not texto:
        return None
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _cuit_valido(d: str) -> bool:
    if len(d) != 11 or not d.isdigit():
        return False
    suma = sum(int(x) * p for x, p in zip(d[:10], _PESOS_CUIT))
    resto = 11 - (suma % 11)
    verif = 0 if resto == 11 else (9 if resto == 10 else resto)
    return verif == int(d[10])


def normalizar_cuit(valor) -> str | None:
    """Devuelve el CUIT/CUIL como 11 dígitos válidos, o None."""
    if valor is None:
        return None
    d = _SOLO_DIGITOS.sub("", str(valor))
    return d if (len(d) == 11 and _cuit_valido(d)) else None


def cuit_enmascarado(d: str | None) -> str | None:
    """Identificador parcial para minimización de datos (Ley 25.326)."""
    if not d or len(d) != 11:
        return None
    return f"{d[:2]}-XXXXXX{d[8:10]}-{d[10]}"


def _slug(texto: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in (texto or "").lower())
    while "--" in base:
        base = base.replace("--", "-")
    return base.strip("-")[:80]


def _hash_id(prefijo: str, *partes) -> str:
    crudo = "|".join(str(p) for p in partes)
    return f"{prefijo}-{hashlib.md5(crudo.encode('utf-8')).hexdigest()[:16]}"


def _int(valor) -> int | None:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _clasificar(nombre: str) -> str | None:
    n = (nombre or "").lower()
    if "bienes" in n:
        return "bienes"
    if "deuda" in n:
        return "deudas"
    if "familiar" in n:
        return "familiares"
    if "consolidado" in n or "declaraciones-juradas" in n:
        return "declaraciones"
    return None


# --------------------------------------------------------------------------
# Extracción (CKAN / archivos locales)
# --------------------------------------------------------------------------

def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ar-acc/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return json.load(resp)


def _descargar(url: str, destino: pathlib.Path) -> bool:
    for intento in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ar-acc/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
                tmp = destino.with_suffix(destino.suffix + ".part")
                with tmp.open("wb") as fh:
                    shutil.copyfileobj(resp, fh)
                tmp.replace(destino)
            return True
        except Exception as exc:  # noqa: BLE001
            espera = 2 ** (intento + 1)
            print(f"  descarga falló ({exc}); reintento en {espera}s")
            time.sleep(espera)
    return False


def localizar_archivos(anio: int, offline: bool) -> dict[str, pathlib.Path]:
    """Devuelve {tipo: ruta_csv} para el año, descargando si hace falta."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    archivos: dict[str, pathlib.Path] = {}

    for csv_path in sorted(RAW_DIR.glob(f"*{anio}*.csv")):
        tipo = _clasificar(csv_path.name)
        if tipo:
            archivos.setdefault(tipo, csv_path)

    if "declaraciones" not in archivos and not offline:
        print(f"[ar-acc] resolviendo recursos CKAN de {DATASET_ID} ...")
        try:
            payload = _http_json(
                f"{PORTAL}/api/3/action/package_show?id={DATASET_ID}")
            recursos = payload.get("result", {}).get("resources", [])
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                f"[ar-acc] No se pudo consultar el portal oficial: {exc}\n"
                f"Descargá los CSV del dataset manualmente desde\n"
                f"  {PORTAL}/dataset/{DATASET_ID}\n"
                f"dejalos en {RAW_DIR}/ y volvé a correr con --offline."
            )
        for rec in recursos:
            nombre, url = rec.get("name", ""), rec.get("url", "")
            if not url or str(anio) not in f"{nombre}{url}":
                continue
            tipo = _clasificar(nombre) or _clasificar(url)
            if not tipo or tipo in archivos:
                continue
            destino = RAW_DIR / f"ddjj-{tipo}-{anio}.csv"
            print(f"  descargando {tipo}: {url}")
            if _descargar(url, destino):
                archivos[tipo] = destino

    if "declaraciones" not in archivos:
        raise SystemExit(
            f"[ar-acc] No se encontró el CSV principal de DDJJ {anio}.\n"
            f"Descargá los archivos del dataset '{DATASET_ID}' desde\n"
            f"  {PORTAL}/dataset/{DATASET_ID}\n"
            f"y dejalos en {RAW_DIR}/ (luego corré con --offline)."
        )
    return archivos


def _leer_csv(path: pathlib.Path | None):
    if not path:
        return
    with path.open(encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


# --------------------------------------------------------------------------
# Transformación
# --------------------------------------------------------------------------

def _periodo(raw: dict) -> str:
    codigo = (raw.get("periodo_inicio_cierre") or "").strip().upper()
    return {"I": "inicio", "C": "cierre"}.get(codigo, codigo.lower() or "n/d")


def transformar(archivos: dict[str, pathlib.Path], anio: int,
                limite: int | None) -> dict[str, list[dict]]:
    """Convierte los CSV crudos en filas listas para cargar."""
    declaraciones: list[dict] = []
    leidas = 0
    for raw in _leer_csv(archivos.get("declaraciones")):
        leidas += 1
        if limite and leidas > limite:
            break
        cuil = normalizar_cuit(raw.get("cuit"))
        dj_id = (raw.get("dj_id") or "").strip()
        if not cuil or not dj_id:
            continue
        total_bienes = normalizar_monto(raw.get("total_bienes_final"))
        total_deudas = normalizar_monto(raw.get("total_deudas_final"))
        patrimonio_neto = None
        if total_bienes is not None:
            patrimonio_neto = total_bienes - (total_deudas or 0.0)
        organismo = (raw.get("organismo") or "").strip()
        anio_raw = (raw.get("anio") or "").strip()
        declaraciones.append({
            "ddjj_id": f"ddjj-{dj_id}",
            "cuil": cuil,
            "cuil_parcial": cuit_enmascarado(cuil),
            "nombre": (raw.get("funcionario_apellido_nombre") or "").strip(),
            "anio": int(anio_raw) if anio_raw.isdigit() else anio,
            "tipo": (raw.get("tipo_declaracion_jurada_descripcion") or "").strip(),
            "rectificativa": _int(raw.get("rectificativa")) or 0,
            "cargo": (raw.get("cargo") or "").strip(),
            "sector": (raw.get("sector") or "").strip(),
            "desde": (raw.get("desde") or "").strip(),
            "proveedor_contratista":
                (raw.get("proveedor_contratista") or "").strip().upper() == "SI",
            "organismo": organismo,
            "organismo_id": f"org-{_slug(organismo)}" if organismo else None,
            "total_bienes": total_bienes,
            "total_deudas": total_deudas,
            "patrimonio_total": total_bienes,
            "patrimonio_neto": patrimonio_neto,
        })

    bienes: list[dict] = []
    for raw in _leer_csv(archivos.get("bienes")):
        dj_id = (raw.get("dj_id") or "").strip()
        if not dj_id:
            continue
        periodo = _periodo(raw)
        descripcion = (raw.get("bien_descripcion") or "").strip()
        tipo = (raw.get("bien_tipo") or "").strip()
        valor = normalizar_monto(raw.get("bien_importe"))
        bienes.append({
            "ddjj_id": f"ddjj-{dj_id}",
            "bien_id": _hash_id("bien", dj_id, periodo, tipo, descripcion, valor),
            "tipo": tipo, "descripcion": descripcion, "valor": valor,
            "origen_fondos": (raw.get("bien_origen_fondos") or "").strip(),
            "titularidad": (raw.get("bien_titularidad") or "").strip(),
            "periodo": periodo,
        })

    deudas: list[dict] = []
    for raw in _leer_csv(archivos.get("deudas")):
        dj_id = (raw.get("dj_id") or "").strip()
        if not dj_id:
            continue
        periodo = _periodo(raw)
        descripcion = (raw.get("deuda_descripcion") or "").strip()
        tipo = (raw.get("deuda_tipo") or "").strip()
        importe = normalizar_monto(raw.get("deuda_importe"))
        deudas.append({
            "ddjj_id": f"ddjj-{dj_id}",
            "deuda_id": _hash_id("deuda", dj_id, periodo, tipo, descripcion, importe),
            "tipo": tipo, "descripcion": descripcion, "importe": importe,
            "clasificacion": (raw.get("deuda_clasificacion") or "").strip(),
            "radicacion": (raw.get("deuda_radicacion_localizacion") or "").strip(),
            "periodo": periodo,
        })

    familiares: list[dict] = []
    for raw in _leer_csv(archivos.get("familiares")):
        cuil_titular = normalizar_cuit(raw.get("cuit"))
        cuil_familiar = normalizar_cuit(raw.get("familiar_cuit"))
        if not cuil_titular or not cuil_familiar:
            continue
        familiares.append({
            "cuil_titular": cuil_titular,
            "cuil_familiar": cuil_familiar,
            "cuil_familiar_parcial": cuit_enmascarado(cuil_familiar),
            "nombre_familiar": (raw.get("familiar_apellido_nombre") or "").strip(),
            "vinculo": (raw.get("familiar_parentesco") or "").strip(),
        })

    return {"declaraciones": declaraciones, "bienes": bienes,
            "deudas": deudas, "familiares": familiares}


# --------------------------------------------------------------------------
# Carga en Neo4j
# --------------------------------------------------------------------------

_CONSTRAINTS = [
    "CREATE CONSTRAINT persona_cuil IF NOT EXISTS "
    "FOR (p:Persona) REQUIRE p.cuil IS UNIQUE",
    "CREATE CONSTRAINT ddjj_id IF NOT EXISTS "
    "FOR (d:DeclaracionJurada) REQUIRE d.ddjj_id IS UNIQUE",
    "CREATE CONSTRAINT bien_id IF NOT EXISTS "
    "FOR (b:BienDeclarado) REQUIRE b.bien_id IS UNIQUE",
    "CREATE CONSTRAINT deuda_id IF NOT EXISTS "
    "FOR (d:Deuda) REQUIRE d.deuda_id IS UNIQUE",
    "CREATE CONSTRAINT organismo_id IF NOT EXISTS "
    "FOR (o:Organismo) REQUIRE o.organismo_id IS UNIQUE",
    "CREATE CONSTRAINT fuente_doc_id IF NOT EXISTS "
    "FOR (f:FuenteDocumento) REQUIRE f.doc_id IS UNIQUE",
]

_LOAD_DECLARACIONES = """
UNWIND $rows AS row
MERGE (p:Persona {cuil: row.cuil})
  SET p.nombre = coalesce(row.nombre, p.nombre),
      p.cuil_parcial = row.cuil_parcial
MERGE (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
  SET d.anio = row.anio, d.tipo = row.tipo,
      d.rectificativa = row.rectificativa, d.cargo = row.cargo,
      d.sector = row.sector, d.desde = row.desde,
      d.proveedor_contratista = row.proveedor_contratista,
      d.total_bienes = row.total_bienes, d.total_deudas = row.total_deudas,
      d.patrimonio_total = row.patrimonio_total,
      d.patrimonio_neto = row.patrimonio_neto
MERGE (p)-[:PRESENTO]->(d)
MERGE (doc:FuenteDocumento {doc_id: row.doc_id})
  SET doc.source_id = 'ddjj', doc.url = row.url,
      doc.fecha_captura = row.fecha_captura
MERGE (d)-[:SEGUN_FUENTE]->(doc)
FOREACH (_ IN CASE WHEN row.organismo_id IS NULL THEN [] ELSE [1] END |
  MERGE (o:Organismo {organismo_id: row.organismo_id})
    ON CREATE SET o.nombre = row.organismo, o.nivel = 'nacional'
  MERGE (d)-[:CARGO_DECLARADO_EN]->(o)
)
"""

_LOAD_BIENES = """
UNWIND $rows AS row
MATCH (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
MERGE (b:BienDeclarado {bien_id: row.bien_id})
  SET b.tipo = row.tipo, b.descripcion = row.descripcion,
      b.valor = row.valor, b.origen_fondos = row.origen_fondos,
      b.titularidad = row.titularidad, b.periodo = row.periodo
MERGE (d)-[:DECLARA]->(b)
"""

_LOAD_DEUDAS = """
UNWIND $rows AS row
MATCH (d:DeclaracionJurada {ddjj_id: row.ddjj_id})
MERGE (de:Deuda {deuda_id: row.deuda_id})
  SET de.tipo = row.tipo, de.descripcion = row.descripcion,
      de.importe = row.importe, de.clasificacion = row.clasificacion,
      de.radicacion = row.radicacion, de.periodo = row.periodo
MERGE (d)-[:REGISTRA_DEUDA]->(de)
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

_LIMPIAR = """
MATCH (n)
WHERE n:Persona OR n:DeclaracionJurada OR n:BienDeclarado
   OR n:Deuda OR n:Organismo OR n:FuenteDocumento
DETACH DELETE n
"""


def _cargar(session, query: str, filas: list[dict], chunk: int = 1000) -> None:
    for i in range(0, len(filas), chunk):
        session.run(query, rows=filas[i:i + chunk])


def cargar(datos: dict[str, list[dict]], *, limpiar: bool, fuente_url: str,
           fecha: str) -> tuple[int, int]:
    """Carga los datos transformados en Neo4j. Devuelve (nodos, relaciones)."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        driver.close()
        raise SystemExit(
            f"[ar-acc] No se pudo conectar a Neo4j en {settings.neo4j_uri}.\n"
            f"Revisá el .env y que la base esté activa. Detalle: {exc}")

    for d in datos["declaraciones"]:
        d["doc_id"] = f"ddjj-doc-{d['ddjj_id']}"
        d["url"] = fuente_url
        d["fecha_captura"] = fecha

    with driver.session(database=settings.neo4j_database) as session:
        if limpiar:
            print("[ar-acc] limpiando datos de DDJJ previos ...")
            session.run(_LIMPIAR)
        for c in _CONSTRAINTS:
            session.run(c)
        print("[ar-acc] cargando declaraciones ...")
        _cargar(session, _LOAD_DECLARACIONES, datos["declaraciones"])
        print("[ar-acc] cargando bienes ...")
        _cargar(session, _LOAD_BIENES, datos["bienes"])
        print("[ar-acc] cargando deudas ...")
        _cargar(session, _LOAD_DEUDAS, datos["deudas"])
        print("[ar-acc] cargando grupo familiar ...")
        _cargar(session, _LOAD_FAMILIARES, datos["familiares"])
        nodos = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    driver.close()
    return nodos, rels


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="import_ddjj_real",
        description="Carga DDJJ patrimoniales reales (datos.jus.gob.ar) en Neo4j.")
    parser.add_argument("--anio", type=int, required=True,
                        help="Año fiscal de las declaraciones a cargar.")
    parser.add_argument("--offline", action="store_true",
                        help="No descargar: usar solo CSV ya presentes en "
                             "data/ddjj/raw/.")
    parser.add_argument("--limpiar", action="store_true",
                        help="Borrar los datos de DDJJ previos antes de cargar.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Limitar la cantidad de declaraciones (pruebas).")
    args = parser.parse_args(argv)

    print(f"[ar-acc] Ingesta de DDJJ reales — año {args.anio}")
    archivos = localizar_archivos(args.anio, args.offline)
    print(f"[ar-acc] archivos: {{{', '.join(archivos)}}}")

    datos = transformar(archivos, args.anio, args.limite)
    print(f"[ar-acc] transformado: {len(datos['declaraciones'])} declaraciones, "
          f"{len(datos['bienes'])} bienes, {len(datos['deudas'])} deudas, "
          f"{len(datos['familiares'])} vínculos familiares")
    if not datos["declaraciones"]:
        raise SystemExit("[ar-acc] No se obtuvo ninguna declaración válida.")

    nodos, rels = cargar(
        datos, limpiar=args.limpiar,
        fuente_url=f"{PORTAL}/dataset/{DATASET_ID}",
        fecha=time.strftime("%Y-%m-%d"))

    print("-" * 64)
    print(f"[ar-acc] Ingesta finalizada. Grafo: {nodos} nodos, {rels} relaciones.")
    print(f"[ar-acc] Abrí el dashboard en /dashboard para explorar.")
    print("-" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
