"""Servicio del dashboard de inconsistencias de ar-acc.

Consulta el grafo de Neo4j construido a partir de las Declaraciones
Juradas Patrimoniales Integrales (Ley 25.188) y expone:

- Navegación jerárquica por secciones (organismos, personas, DDJJ).
- Un motor de detección de inconsistencias sobre datos declarados.

PRINCIPIO RECTOR (igual que `aracc/queries/deteccion.cypher`):
cada hallazgo es una HIPÓTESIS a verificar contra la fuente oficial
citada. No constituye prueba ni imputación. Rige la presunción de
inocencia.

El grafo lo pueblan:
  - `pipelines/import_ddjj_real.py`  (datos públicos reales)
  - `dashboard/seed_demo.cypher`     (datos sintéticos de demostración)
"""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from config.settings import settings

# Errores que el dashboard convierte en un mensaje legible.
_CONEXION = (Neo4jError, DriverError, OSError, ValueError)

# --------------------------------------------------------------------------
# Umbrales de detección (ajustables)
# --------------------------------------------------------------------------

UMBRAL_SALTO = 0.5          # +50% interanual de patrimonio
TOLERANCIA_DESCUADRE = 0.10  # 10% de brecha entre total declarado y suma de bienes
LIMITE_RANKING = 60

# --------------------------------------------------------------------------
# Metadatos de los detectores
# --------------------------------------------------------------------------

DETECTORES: dict[str, dict[str, str]] = {
    "salto-patrimonial": {
        "titulo": "Salto patrimonial interanual",
        "descripcion": "El patrimonio declarado crece más de un 50% entre dos "
                       "DDJJ de años consecutivos.",
    },
    "descuadre-interno": {
        "titulo": "Descuadre dentro de la declaración",
        "descripcion": "El total de bienes declarado no coincide con la suma de "
                       "los bienes individuales informados en la misma DDJJ.",
    },
    "funcionario-proveedor": {
        "titulo": "Funcionario marcado como proveedor del Estado",
        "descripcion": "La persona declaró ser proveedora/contratista del "
                       "Estado mientras ejercía un cargo público.",
    },
    "anios-faltantes": {
        "titulo": "Años sin declaración presentada",
        "descripcion": "Hay años intermedios sin DDJJ entre dos declaraciones "
                       "presentadas (posible omisión de presentación).",
    },
    "rectificativa": {
        "titulo": "Declaración rectificada",
        "descripcion": "La DDJJ fue rectificada después de su presentación "
                       "original.",
    },
}


# --------------------------------------------------------------------------
# Helpers de formato
# --------------------------------------------------------------------------

def _money(valor: Any) -> str:
    if valor is None:
        return "s/d"
    try:
        return "$ " + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def _pct(ratio: Any) -> str:
    try:
        return f"+{float(ratio) * 100:.0f}%"
    except (TypeError, ValueError):
        return "s/d"


# --------------------------------------------------------------------------
# Driver Neo4j (singleton perezoso)
# --------------------------------------------------------------------------

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


# --------------------------------------------------------------------------
# Cypher de los detectores
# --------------------------------------------------------------------------

def _q_salto(cuil_filter: str) -> str:
    return f"""
    MATCH (p:Persona)-[:PRESENTO]->(d1:DeclaracionJurada)
    MATCH (p)-[:PRESENTO]->(d2:DeclaracionJurada)
    WHERE d2.anio = d1.anio + 1
      AND d1.patrimonio_total > 0
      AND d2.patrimonio_total IS NOT NULL{cuil_filter}
    WITH p, d1, d2,
         d2.patrimonio_total - d1.patrimonio_total AS delta,
         (d2.patrimonio_total - d1.patrimonio_total) / d1.patrimonio_total AS ratio
    WHERE ratio >= $umbral
    OPTIONAL MATCH (d2)-[:SEGUN_FUENTE]->(f:FuenteDocumento)
    RETURN p.cuil AS cuil,
           coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
           d1.anio AS anio_desde, d2.anio AS anio_hasta,
           d1.patrimonio_total AS pat_desde, d2.patrimonio_total AS pat_hasta,
           delta, ratio, f.url AS fuente
    ORDER BY ratio DESC
    LIMIT $limite
    """


def _q_descuadre(cuil_filter: str) -> str:
    return f"""
    MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
    WHERE d.total_bienes IS NOT NULL AND d.total_bienes > 0{cuil_filter}
    OPTIONAL MATCH (d)-[:DECLARA]->(b:BienDeclarado)
    WHERE b.periodo IN ['cierre', 'n/d']
    WITH p, d, sum(coalesce(b.valor, 0.0)) AS suma, count(b) AS nb
    WHERE nb > 0
      AND abs(d.total_bienes - suma) / d.total_bienes >= $tol
    OPTIONAL MATCH (d)-[:SEGUN_FUENTE]->(f:FuenteDocumento)
    RETURN p.cuil AS cuil,
           coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
           d.anio AS anio, d.total_bienes AS declarado, suma AS sumado,
           abs(d.total_bienes - suma) AS brecha, f.url AS fuente
    ORDER BY brecha DESC
    LIMIT $limite
    """


def _q_proveedor(cuil_filter: str) -> str:
    return f"""
    MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
    WHERE d.proveedor_contratista = true{cuil_filter}
    OPTIONAL MATCH (d)-[:CARGO_DECLARADO_EN]->(o:Organismo)
    RETURN p.cuil AS cuil,
           coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
           d.anio AS anio, d.cargo AS cargo, o.nombre AS organismo
    ORDER BY d.anio DESC
    LIMIT $limite
    """


def _q_rectificativa(cuil_filter: str) -> str:
    return f"""
    MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
    WHERE (coalesce(d.rectificativa, 0) > 0
           OR toLower(coalesce(d.tipo, '')) CONTAINS 'rectif'){cuil_filter}
    OPTIONAL MATCH (d)-[:SEGUN_FUENTE]->(f:FuenteDocumento)
    RETURN p.cuil AS cuil,
           coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
           d.anio AS anio, coalesce(d.rectificativa, 0) AS n_rect,
           d.tipo AS tipo, f.url AS fuente
    ORDER BY d.anio DESC
    LIMIT $limite
    """


def _q_anios_faltantes(cuil_filter: str) -> str:
    return f"""
    MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
    WHERE d.anio IS NOT NULL{cuil_filter}
    WITH p, collect(DISTINCT d.anio) AS anios
    WHERE size(anios) >= 2
    WITH p, anios,
         [a IN anios WHERE NOT (a + 1) IN anios
                       AND any(x IN anios WHERE x > a)] AS con_hueco
    WHERE size(con_hueco) > 0
    RETURN p.cuil AS cuil,
           coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
           anios
    ORDER BY size(anios) DESC
    LIMIT $limite
    """


# --------------------------------------------------------------------------
# Servicio
# --------------------------------------------------------------------------

class DashboardService:
    """Capa de acceso al grafo para el dashboard estilo terminal."""

    # ---- API pública -----------------------------------------------------

    def navegar(self, path: str, q: str | None = None) -> dict:
        """Resuelve una ruta jerárquica y devuelve la vista correspondiente."""
        parts = [p for p in (path or "/").strip("/").split("/") if p]
        try:
            with get_driver().session(database=settings.neo4j_database) as s:
                return self._resolver(s, parts, q)
        except _CONEXION as exc:
            return _vista(
                "/" + "/".join(parts),
                "ERROR DE CONEXIÓN",
                "error",
                note=f"No se pudo consultar Neo4j ({settings.neo4j_uri}). "
                     f"Verificá el .env y que la base esté activa. Detalle: {exc}",
            )

    def buscar(self, q: str) -> dict:
        try:
            with get_driver().session(database=settings.neo4j_database) as s:
                return self._personas(s, q)
        except _CONEXION as exc:
            return _vista("/personas", "BÚSQUEDA", "error",
                          note=f"Error de conexión: {exc}")

    # ---- Ruteo -----------------------------------------------------------

    def _resolver(self, s, parts: list[str], q: str | None) -> dict:
        if not parts:
            return self._root(s)
        head = parts[0]
        if head == "panel":
            return self._panel(s)
        if head == "organismos":
            if len(parts) == 1:
                return self._organismos(s)
            if len(parts) == 2:
                return self._personas_de_organismo(s, parts[1])
            return self._persona(s, parts[2])
        if head == "personas":
            if len(parts) == 1:
                return self._personas(s, q)
            if len(parts) == 2:
                return self._persona(s, parts[1])
            return self._ddjj(s, parts[1], parts[2])
        if head == "inconsistencias":
            if len(parts) == 1:
                return self._inconsistencias(s)
            if len(parts) == 2:
                return self._ranking(s, parts[1])
            return self._persona(s, parts[2])
        return _vista("/" + "/".join(parts), "RUTA DESCONOCIDA", "error",
                      note=f"No existe la sección /{'/'.join(parts)}")

    # ---- Vistas ----------------------------------------------------------

    def _root(self, s) -> dict:
        c = s.run(
            """
            OPTIONAL MATCH (p:Persona) WITH count(p) AS personas
            OPTIONAL MATCH (d:DeclaracionJurada) WITH personas, count(d) AS ddjj
            OPTIONAL MATCH (o:Organismo)
            RETURN personas, ddjj, count(o) AS organismos
            """
        ).single()
        personas = c["personas"] if c else 0
        ddjj = c["ddjj"] if c else 0
        organismos = c["organismos"] if c else 0
        n_inc = self._contar_inconsistencias(s)

        note = ("Grafo vacío. Cargá datos con `python pipelines/import_ddjj_real.py "
                "--anio 2023` (datos reales) o aplicá `dashboard/seed_demo.cypher` "
                "(demo).") if ddjj == 0 else None

        entries = [
            _entry("panel", "panel", "Panel general del sistema",
                   "/panel", "vista", "resumen"),
            _entry("organismos", "organismos", "Organismos del Estado",
                   "/organismos", "seccion", f"{organismos}"),
            _entry("personas", "personas", "Funcionarios con DDJJ",
                   "/personas", "seccion", f"{personas}"),
            _entry("inconsistencias", "inconsistencias",
                   "Inconsistencias detectadas", "/inconsistencias",
                   "alerta", f"{n_inc}"),
        ]
        return _vista("/", "ar-acc :: sistema de transparencia", "raiz",
                      entries=entries, note=note)

    def _panel(self, s) -> dict:
        c = s.run(
            """
            OPTIONAL MATCH (p:Persona) WITH count(p) AS personas
            OPTIONAL MATCH (d:DeclaracionJurada)
              WITH personas, count(d) AS ddjj,
                   min(d.anio) AS anio_min, max(d.anio) AS anio_max
            OPTIONAL MATCH (o:Organismo) WITH personas, ddjj, anio_min, anio_max,
                   count(o) AS organismos
            OPTIONAL MATCH (b:BienDeclarado) WITH personas, ddjj, anio_min,
                   anio_max, organismos, count(b) AS bienes
            OPTIONAL MATCH (de:Deuda)
            RETURN personas, ddjj, anio_min, anio_max, organismos, bienes,
                   count(de) AS deudas
            """
        ).single()
        rango = "s/d"
        if c and c["anio_min"] is not None:
            rango = (f"{c['anio_min']}" if c["anio_min"] == c["anio_max"]
                     else f"{c['anio_min']}–{c['anio_max']}")
        detail = [
            _row("Funcionarios con DDJJ", str(c["personas"] if c else 0)),
            _row("Declaraciones juradas", str(c["ddjj"] if c else 0)),
            _row("Años cubiertos", rango),
            _row("Organismos", str(c["organismos"] if c else 0)),
            _row("Bienes declarados", str(c["bienes"] if c else 0)),
            _row("Deudas registradas", str(c["deudas"] if c else 0)),
        ]
        resumen = self._resumen_por_tipo(s)
        signals = [
            _signal(tipo, "media",
                    f"{DETECTORES[tipo]['titulo']}: {n} caso(s)",
                    DETECTORES[tipo]["descripcion"], [], None)
            for tipo, n in resumen.items() if n > 0
        ]
        return _vista("/panel", "Panel general", "vista",
                      detail=detail, signals=signals,
                      note="Resumen del grafo cargado y de las señales de riesgo "
                           "detectadas. Cada señal es una hipótesis a verificar.")

    def _organismos(self, s) -> dict:
        rows = s.run(
            """
            MATCH (o:Organismo)<-[:CARGO_DECLARADO_EN]-(d:DeclaracionJurada)
            OPTIONAL MATCH (d)<-[:PRESENTO]-(p:Persona)
            WITH o, count(DISTINCT d) AS ddjj, count(DISTINCT p) AS personas
            RETURN o.organismo_id AS oid, o.nombre AS nombre, personas, ddjj
            ORDER BY personas DESC, nombre
            LIMIT 150
            """
        )
        entries = [
            _entry(r["oid"], r["nombre"] or r["oid"],
                   f"{r['personas']} funcionario(s) · {r['ddjj']} DDJJ",
                   f"/organismos/{r['oid']}", "seccion", f"{r['personas']}")
            for r in rows
        ]
        return _vista("/organismos", "Organismos del Estado", "seccion",
                      entries=entries,
                      note=None if entries else "No hay organismos cargados.")

    def _personas_de_organismo(self, s, oid: str) -> dict:
        rows = s.run(
            """
            MATCH (o:Organismo {organismo_id: $oid})<-[:CARGO_DECLARADO_EN]-
                  (d:DeclaracionJurada)<-[:PRESENTO]-(p:Persona)
            WITH o, p, collect(DISTINCT d) AS djs
            RETURN o.nombre AS organismo, p.cuil AS cuil,
                   coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
                   size(djs) AS n,
                   [x IN djs | x.anio] AS anios,
                   any(x IN djs WHERE x.proveedor_contratista) AS prov,
                   any(x IN djs WHERE coalesce(x.rectificativa, 0) > 0) AS rect,
                   any(d1 IN djs WHERE any(d2 IN djs
                       WHERE d2.anio = d1.anio + 1 AND d1.patrimonio_total > 0
                         AND d2.patrimonio_total IS NOT NULL
                         AND (d2.patrimonio_total - d1.patrimonio_total)
                             / d1.patrimonio_total >= $umbral)) AS salto
            ORDER BY nombre
            LIMIT 300
            """,
            oid=oid, umbral=UMBRAL_SALTO,
        )
        entries = []
        organismo = oid
        for r in rows:
            organismo = r["organismo"] or oid
            flags = sum([bool(r["prov"]), bool(r["rect"]), bool(r["salto"])])
            anios = sorted(a for a in r["anios"] if a is not None)
            rango = (f"{anios[0]}–{anios[-1]}" if len(anios) > 1
                     else (str(anios[0]) if anios else "s/d"))
            entries.append(_entry(
                r["cuil"], r["nombre"],
                f"{r['n']} DDJJ · {rango}",
                f"/organismos/{oid}/{r['cuil']}", "persona",
                f"⚠{flags}" if flags else "ok"))
        return _vista(f"/organismos/{oid}", organismo, "seccion",
                      entries=entries,
                      note=None if entries else "Sin funcionarios en este organismo.")

    def _personas(self, s, q: str | None) -> dict:
        q = (q or "").strip()
        if q:
            rows = s.run(
                """
                MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
                WHERE toLower(coalesce(p.nombre, '')) CONTAINS toLower($q)
                   OR coalesce(p.cuil_parcial, '') CONTAINS $q
                   OR p.cuil CONTAINS $q
                WITH p, collect(DISTINCT d) AS djs
                RETURN p.cuil AS cuil,
                       coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
                       size(djs) AS n, [x IN djs | x.anio] AS anios
                ORDER BY nombre
                LIMIT 200
                """, q=q)
        else:
            rows = s.run(
                """
                MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
                WITH p, collect(DISTINCT d) AS djs
                RETURN p.cuil AS cuil,
                       coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
                       size(djs) AS n, [x IN djs | x.anio] AS anios
                ORDER BY nombre
                LIMIT 200
                """)
        entries = []
        for r in rows:
            anios = sorted(a for a in r["anios"] if a is not None)
            rango = (f"{anios[0]}–{anios[-1]}" if len(anios) > 1
                     else (str(anios[0]) if anios else "s/d"))
            entries.append(_entry(
                r["cuil"], r["nombre"], f"{r['n']} DDJJ · {rango}",
                f"/personas/{r['cuil']}", "persona", f"{r['n']}"))
        titulo = f"Personas que coinciden con «{q}»" if q else "Funcionarios con DDJJ"
        note = None
        if not entries:
            note = (f"Sin resultados para «{q}»." if q
                    else "No hay personas cargadas en el grafo.")
        return _vista("/personas", titulo, "seccion", entries=entries, note=note)

    def _persona(self, s, cuil: str) -> dict:
        cab = s.run(
            """
            MATCH (p:Persona {cuil: $cuil})
            OPTIONAL MATCH (p)-[:PRESENTO]->(d:DeclaracionJurada)
            OPTIONAL MATCH (d)-[:CARGO_DECLARADO_EN]->(o:Organismo)
            WITH p, d, o ORDER BY d.anio
            RETURN coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
                   p.cuil_parcial AS cuil_parcial, p.provincia AS provincia,
                   collect(DISTINCT {anio: d.anio, ddjj_id: d.ddjj_id,
                           tipo: d.tipo, cargo: d.cargo,
                           organismo: o.nombre,
                           patrimonio: d.patrimonio_total}) AS djs
            """, cuil=cuil).single()
        if not cab or not cab["nombre"]:
            return _vista(f"/personas/{cuil}", "PERSONA NO ENCONTRADA", "error",
                          note=f"No hay ninguna persona con CUIL/CUIL parcial {cuil}.")

        djs = [d for d in cab["djs"] if d.get("ddjj_id")]
        djs.sort(key=lambda d: d.get("anio") or 0)
        cargos = sorted({d["cargo"] for d in djs if d.get("cargo")})
        organismos = sorted({d["organismo"] for d in djs if d.get("organismo")})
        anios = [d["anio"] for d in djs if d.get("anio") is not None]

        detail = [
            _row("Identificador (parcial)", cab["cuil_parcial"] or cuil),
            _row("Declaraciones presentadas", str(len(djs))),
            _row("Años", f"{min(anios)}–{max(anios)}" if anios else "s/d"),
            _row("Cargos declarados", " · ".join(cargos) if cargos else "s/d"),
            _row("Organismos", " · ".join(organismos) if organismos else "s/d"),
        ]
        entries = [
            _entry(d["ddjj_id"],
                   f"DDJJ {d.get('anio', 's/d')}",
                   f"{d.get('tipo') or 'Declaración'} · "
                   f"patrimonio {_money(d.get('patrimonio'))}",
                   f"/personas/{cuil}/{d['ddjj_id']}", "ddjj",
                   str(d.get("anio") or ""))
            for d in djs
        ]
        signals = self._signals_persona(s, cuil)
        return _vista(f"/personas/{cuil}", cab["nombre"], "persona",
                      detail=detail, entries=entries, signals=signals,
                      note="DDJJ presentadas por la persona. Las señales de abajo "
                           "son hipótesis a verificar contra la fuente oficial.")

    def _ddjj(self, s, cuil: str, ddjj_id: str) -> dict:
        cab = s.run(
            """
            MATCH (p:Persona {cuil: $cuil})-[:PRESENTO]->
                  (d:DeclaracionJurada {ddjj_id: $ddjj_id})
            OPTIONAL MATCH (d)-[:CARGO_DECLARADO_EN]->(o:Organismo)
            OPTIONAL MATCH (d)-[:SEGUN_FUENTE]->(f:FuenteDocumento)
            RETURN coalesce(p.nombre, p.cuil_parcial, p.cuil) AS nombre,
                   d.anio AS anio, d.tipo AS tipo, d.cargo AS cargo,
                   d.sector AS sector, d.desde AS desde,
                   d.proveedor_contratista AS proveedor,
                   d.rectificativa AS rectificativa,
                   d.total_bienes AS total_bienes, d.total_deudas AS total_deudas,
                   d.patrimonio_total AS patrimonio_total,
                   d.patrimonio_neto AS patrimonio_neto,
                   o.nombre AS organismo, f.url AS fuente
            """, cuil=cuil, ddjj_id=ddjj_id).single()
        if not cab:
            return _vista(f"/personas/{cuil}/{ddjj_id}", "DDJJ NO ENCONTRADA",
                          "error", note=f"No existe la declaración {ddjj_id}.")

        detail = [
            _row("Funcionario", cab["nombre"]),
            _row("Año fiscal", str(cab["anio"] or "s/d")),
            _row("Tipo", cab["tipo"] or "s/d"),
            _row("Cargo", cab["cargo"] or "s/d"),
            _row("Organismo", cab["organismo"] or "s/d"),
            _row("Sector", cab["sector"] or "s/d"),
            _row("En el cargo desde", cab["desde"] or "s/d"),
            _row("Total bienes", _money(cab["total_bienes"])),
            _row("Total deudas", _money(cab["total_deudas"])),
            _row("Patrimonio total", _money(cab["patrimonio_total"])),
            _row("Patrimonio neto", _money(cab["patrimonio_neto"])),
            _row("¿Proveedor del Estado?", "SÍ" if cab["proveedor"] else "No"),
            _row("Rectificativa", "Sí" if (cab["rectificativa"] or 0) else "No"),
            _row("Fuente oficial", cab["fuente"] or "s/d"),
        ]
        bienes = s.run(
            """
            MATCH (:DeclaracionJurada {ddjj_id: $ddjj_id})-[:DECLARA]->(b:BienDeclarado)
            RETURN b.tipo AS tipo, b.descripcion AS descripcion,
                   b.valor AS valor, b.periodo AS periodo, b.titularidad AS titularidad
            ORDER BY b.valor DESC
            """, ddjj_id=ddjj_id)
        deudas = s.run(
            """
            MATCH (:DeclaracionJurada {ddjj_id: $ddjj_id})-[:REGISTRA_DEUDA]->(de:Deuda)
            RETURN de.tipo AS tipo, de.descripcion AS descripcion,
                   de.importe AS importe, de.periodo AS periodo
            ORDER BY de.importe DESC
            """, ddjj_id=ddjj_id)
        entries = []
        for b in bienes:
            entries.append(_entry(
                "", f"[BIEN] {b['tipo'] or 'Bien'}",
                f"{b['descripcion'] or 's/d'} · {_money(b['valor'])} "
                f"· {b['periodo'] or ''}".strip(" ·"),
                "", "item", ""))
        for d in deudas:
            entries.append(_entry(
                "", f"[DEUDA] {d['tipo'] or 'Deuda'}",
                f"{d['descripcion'] or 's/d'} · {_money(d['importe'])}",
                "", "item", ""))
        signals = self._signals_persona(s, cuil, ddjj_anio=cab["anio"])
        return _vista(f"/personas/{cuil}/{ddjj_id}",
                      f"DDJJ {cab['anio']} · {cab['nombre']}", "ddjj",
                      detail=detail, entries=entries, signals=signals,
                      note="Detalle de la declaración jurada y sus bienes/deudas.")

    def _inconsistencias(self, s) -> dict:
        resumen = self._resumen_por_tipo(s)
        entries = [
            _entry(tipo, DETECTORES[tipo]["titulo"],
                   DETECTORES[tipo]["descripcion"],
                   f"/inconsistencias/{tipo}", "alerta", str(resumen.get(tipo, 0)))
            for tipo in DETECTORES
        ]
        total = sum(resumen.values())
        return _vista("/inconsistencias", "Inconsistencias detectadas", "seccion",
                      entries=entries,
                      note=f"{total} señal(es) en total. Cada señal es una "
                           f"HIPÓTESIS a verificar contra la fuente oficial; no "
                           f"constituye prueba ni imputación.")

    def _ranking(self, s, tipo: str) -> dict:
        if tipo not in DETECTORES:
            return _vista(f"/inconsistencias/{tipo}", "DETECTOR DESCONOCIDO",
                          "error", note=f"No existe el detector «{tipo}».")
        casos = self._correr_detector(s, tipo, limite=LIMITE_RANKING)
        entries = []
        for c in casos:
            entries.append(_entry(
                c["cuil"], c["nombre"], c["resumen"],
                f"/inconsistencias/{tipo}/{c['cuil']}", "persona",
                c["severidad"][:4]))
        meta = DETECTORES[tipo]
        return _vista(f"/inconsistencias/{tipo}", meta["titulo"], "seccion",
                      entries=entries, note=meta["descripcion"]
                      + (" — Sin casos detectados." if not entries else ""))

    # ---- Motor de detección ---------------------------------------------

    def _correr_detector(self, s, tipo: str, cuil: str | None = None,
                         limite: int = LIMITE_RANKING) -> list[dict]:
        """Ejecuta un detector y devuelve filas con resumen y señal."""
        cf = " AND p.cuil = $cuil" if cuil else ""
        params: dict[str, Any] = {"limite": limite}
        if cuil:
            params["cuil"] = cuil

        casos: list[dict] = []
        if tipo == "salto-patrimonial":
            params["umbral"] = UMBRAL_SALTO
            for r in s.run(_q_salto(cf), **params):
                casos.append({
                    "cuil": r["cuil"], "nombre": r["nombre"],
                    "severidad": "alta" if r["ratio"] >= 1.0 else "media",
                    "resumen": f"Patrimonio {r['anio_desde']}→{r['anio_hasta']}: "
                               f"{_money(r['pat_desde'])} → {_money(r['pat_hasta'])} "
                               f"({_pct(r['ratio'])})",
                    "titulo": "Salto patrimonial interanual",
                    "detalle": f"Entre {r['anio_desde']} y {r['anio_hasta']} el "
                               f"patrimonio declarado creció {_pct(r['ratio'])}.",
                    "evidencia": [
                        f"Patrimonio {r['anio_desde']}: {_money(r['pat_desde'])}",
                        f"Patrimonio {r['anio_hasta']}: {_money(r['pat_hasta'])}",
                        f"Variación: {_pct(r['ratio'])} ({_money(r['delta'])})",
                    ],
                    "fuente": r["fuente"], "anio": r["anio_hasta"],
                })
        elif tipo == "descuadre-interno":
            params["tol"] = TOLERANCIA_DESCUADRE
            for r in s.run(_q_descuadre(cf), **params):
                casos.append({
                    "cuil": r["cuil"], "nombre": r["nombre"],
                    "severidad": "media",
                    "resumen": f"DDJJ {r['anio']}: declara {_money(r['declarado'])} "
                               f"pero los bienes suman {_money(r['sumado'])}",
                    "titulo": "Descuadre dentro de la declaración",
                    "detalle": f"En la DDJJ {r['anio']} el total de bienes "
                               f"declarado no coincide con la suma de los bienes "
                               f"individuales informados.",
                    "evidencia": [
                        f"Total de bienes declarado: {_money(r['declarado'])}",
                        f"Suma de bienes individuales: {_money(r['sumado'])}",
                        f"Brecha: {_money(r['brecha'])}",
                    ],
                    "fuente": r["fuente"], "anio": r["anio"],
                })
        elif tipo == "funcionario-proveedor":
            for r in s.run(_q_proveedor(cf), **params):
                casos.append({
                    "cuil": r["cuil"], "nombre": r["nombre"],
                    "severidad": "alta",
                    "resumen": f"DDJJ {r['anio']}: declarado como proveedor del "
                               f"Estado ({r['cargo'] or 's/cargo'})",
                    "titulo": "Funcionario marcado como proveedor del Estado",
                    "detalle": f"En la DDJJ {r['anio']} la persona figura como "
                               f"proveedora/contratista del Estado mientras "
                               f"ejercía el cargo «{r['cargo'] or 's/d'}».",
                    "evidencia": [
                        f"Año: {r['anio']}",
                        f"Cargo declarado: {r['cargo'] or 's/d'}",
                        f"Organismo: {r['organismo'] or 's/d'}",
                        "Posible incompatibilidad — Ley 25.188, art. 13.",
                    ],
                    "fuente": None, "anio": r["anio"],
                })
        elif tipo == "rectificativa":
            for r in s.run(_q_rectificativa(cf), **params):
                casos.append({
                    "cuil": r["cuil"], "nombre": r["nombre"],
                    "severidad": "baja",
                    "resumen": f"DDJJ {r['anio']} rectificada "
                               f"({r['tipo'] or 'rectificativa'})",
                    "titulo": "Declaración rectificada",
                    "detalle": f"La DDJJ {r['anio']} fue rectificada después de "
                               f"su presentación original.",
                    "evidencia": [
                        f"Año: {r['anio']}",
                        f"Tipo: {r['tipo'] or 's/d'}",
                        f"Rectificaciones: {r['n_rect']}",
                    ],
                    "fuente": r["fuente"], "anio": r["anio"],
                })
        elif tipo == "anios-faltantes":
            for r in s.run(_q_anios_faltantes(cf), **params):
                anios = sorted(a for a in r["anios"] if a is not None)
                faltan = [a + 1 for a in anios
                          if (a + 1) not in anios and any(x > a for x in anios)]
                casos.append({
                    "cuil": r["cuil"], "nombre": r["nombre"],
                    "severidad": "media",
                    "resumen": f"Años sin DDJJ: {', '.join(map(str, faltan))}",
                    "titulo": "Años sin declaración presentada",
                    "detalle": "Hay años intermedios sin DDJJ entre dos "
                               "declaraciones presentadas.",
                    "evidencia": [
                        f"Años con DDJJ: {', '.join(map(str, anios))}",
                        f"Años faltantes: {', '.join(map(str, faltan))}",
                    ],
                    "fuente": None, "anio": faltan[0] if faltan else None,
                })
        return casos

    def _signals_persona(self, s, cuil: str,
                         ddjj_anio: int | None = None) -> list[dict]:
        """Todas las señales que afectan a una persona (opcionalmente a un año)."""
        signals: list[dict] = []
        for tipo in DETECTORES:
            for c in self._correr_detector(s, tipo, cuil=cuil, limite=50):
                if ddjj_anio is not None and c.get("anio") not in (None, ddjj_anio):
                    continue
                signals.append(_signal(
                    tipo, c["severidad"], c["titulo"], c["detalle"],
                    c["evidencia"], c["fuente"]))
        return signals

    def _resumen_por_tipo(self, s) -> dict[str, int]:
        return {tipo: len(self._correr_detector(s, tipo, limite=1000))
                for tipo in DETECTORES}

    def _contar_inconsistencias(self, s) -> int:
        try:
            return sum(self._resumen_por_tipo(s).values())
        except _CONEXION:
            return 0


# --------------------------------------------------------------------------
# Constructores de la respuesta
# --------------------------------------------------------------------------

def _vista(path: str, title: str, kind: str, *, entries: list | None = None,
           detail: list | None = None, signals: list | None = None,
           note: str | None = None) -> dict:
    out = {"path": path, "title": title, "kind": kind,
           "entries": entries or [], "detail": detail or [],
           "signals": signals or []}
    if note:
        out["note"] = note
    return out


def _entry(key: str, label: str, sublabel: str, path: str,
           kind: str, badge: str) -> dict:
    return {"key": key, "label": label, "sublabel": sublabel,
            "path": path, "kind": kind, "badge": badge}


def _row(label: str, value: str) -> dict:
    return {"label": label, "value": value}


def _signal(tipo: str, severidad: str, titulo: str, detalle: str,
            evidencia: list[str], fuente: str | None) -> dict:
    return {"tipo": tipo, "severidad": severidad, "titulo": titulo,
            "detalle": detalle, "evidencia": evidencia, "fuente": fuente}
