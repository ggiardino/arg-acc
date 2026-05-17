# ar-acc — Argentina Transparency Graph (WTG-AR)

> **Grafo de conocimiento abierto que cruza las bases de datos públicas de
> Argentina para detectar incompatibilidades patrimoniales, redes de
> contratistas, sobreprecios, conflictos de interés y señales de riesgo en
> los tres niveles del Estado (nacional, provincial y municipal).**

Adaptación argentina del proyecto brasileño
[`br-acc`](https://github.com/brunoclz/br-acc). Conserva su arquitectura
probada (Neo4j + FastAPI + ETL idempotente + frontend React) y la
re-territorializa para el ecosistema de datos públicos argentino:
identificadores (CUIT/CUIL/DNI), fuentes (datos.gob.ar, COMPR.AR,
CONTRAT.AR, Oficina Anticorrupción, AFIP/ARCA, Boletín Oficial, CNE) y
marco legal (Ley 27.275 de Acceso a la Información Pública y Ley 25.326 de
Protección de los Datos Personales).

`ar-acc` **no interpreta ni acusa**: normaliza datos ya públicos pero
dispersos y expone conexiones. Cada señal de riesgo es una *hipótesis
verificable* con trazabilidad completa a la fuente oficial.

---

## 1. Estructura de carpetas del repositorio

```
ar-acc/
├── api/                          # Backend FastAPI (REST + GraphQL)
│   └── src/aracc/
│       ├── main.py               # App factory, middlewares, routers
│       ├── config.py             # Settings (pydantic-settings)
│       ├── constants.py          # Labels, rel-types, score weights
│       ├── dependencies.py       # DI: driver Neo4j, auth, rate-limit
│       ├── middleware/
│       │   ├── doc_masking.py    # Enmascara CUIT/CUIL/DNI en modo público
│       │   ├── rate_limit.py
│       │   └── security_headers.py
│       ├── models/               # Schemas Pydantic (entity, graph, ...)
│       ├── routers/              # entity, graph, search, patterns,
│       │                         #   investigation, baseline, public, meta
│       ├── graphql/              # Schema Strawberry (capa GraphQL)
│       ├── services/             # neo4j_service, score_service,
│       │                         #   source_registry, public_guard, ...
│       └── queries/*.cypher      # Cypher parametrizado (1 archivo = 1 query)
│
├── etl/                          # Pipelines de ingesta
│   └── src/aracc_etl/
│       ├── base.py               # Clase Pipeline (extract/transform/load)
│       ├── runner.py             # CLI: `aracc-etl run <source>`
│       ├── loader.py             # Neo4jBatchLoader (UNWIND, idempotente)
│       ├── flows.py              # Flujos Prefect (scheduling)
│       ├── sources.yml           # Registro declarativo de fuentes
│       ├── pipelines/            # 1 módulo por fuente
│       │   ├── datos_gob_ar.py
│       │   ├── comprar.py        # COMPR.AR (compras públicas nacionales)
│       │   ├── contratar.py      # CONTRAT.AR (obra pública)
│       │   ├── declaraciones_juradas.py   # Oficina Anticorrupción
│       │   ├── afip_padron.py    # Padrón CUIT / estados administrativos
│       │   ├── boletin_oficial.py
│       │   ├── cne_candidatos.py # Cámara Nacional Electoral
│       │   ├── cne_aportes.py    # Aportes de campaña
│       │   ├── presupuesto_abierto.py
│       │   ├── georef.py         # Normalización geográfica (API Georef)
│       │   ├── justicia.py       # Datos abiertos del Poder Judicial
│       │   └── provincial/       # Sub-paquete por jurisdicción
│       │       ├── caba.py
│       │       ├── pba.py        # Provincia de Buenos Aires
│       │       └── ...
│       ├── entity_resolution/    # Linkage probabilístico de identidades
│       ├── schemas/              # Validación de contratos de datos
│       └── transforms/           # Normalización (CUIT, fechas, montos)
│
├── frontend/                     # SPA React + Vite (TypeScript)
│   └── src/                      # Búsqueda, explorador de grafo, patrones
│
├── infra/
│   ├── neo4j/init-aracc.cypher   # Constraints + índices
│   ├── docker-compose.yml        # Stack local (Neo4j, API, frontend)
│   ├── docker-compose.prod.yml
│   └── scripts/                  # backup, seed, deploy, healthcheck
│
├── analytics/                    # GDS (Graph Data Science) + ML
│   ├── gds_projections.cypher    # Proyecciones para community detection
│   └── models/                   # Scoring de riesgo (fase Avanzada)
│
├── config/
│   ├── bootstrap_contract.yml    # Contrato de datos del bootstrap
│   └── detection_rules.yml       # Reglas de detección declarativas
│
├── data/                         # Datos crudos/derivados (gitignored)
├── docs/
│   ├── ar-acc/                   # Esta documentación
│   │   ├── ARQUITECTURA.md
│   │   ├── datasets-ar.md
│   │   ├── roadmap.md
│   │   └── legal/
│   └── data-sources.md
├── scripts/                      # bootstrap, auditoría, checks de CI
├── .github/                      # Workflows CI/CD, issue templates
├── docker-compose.yml
├── Makefile
├── DISCLAIMER.md  PRIVACY.md  LEY-25326.md  TERMS.md  ETHICS.md
└── README.md
```

**Cambios estructurales frente a `br-acc`:**

| `br-acc`                       | `ar-acc`                                   |
|--------------------------------|--------------------------------------------|
| paquete `bracc` / `bracc_etl`  | paquete `aracc` / `aracc_etl`               |
| `LGPD.md`                      | `LEY-25326.md` (Protección de Datos)        |
| ETL ad-hoc / Makefile          | + `etl/flows.py` con **Prefect** schedulable|
| solo REST                      | + capa **GraphQL** (`api/src/aracc/graphql`)|
| —                              | + `analytics/` con **Neo4j GDS** + ML       |
| —                              | + `pipelines/provincial/` (federalismo)     |

---

## 2. Schema inicial del grafo Neo4j

El esquema completo y aplicable está en
[`aracc/schema/init-neo4j.cypher`](../../aracc/schema/init-neo4j.cypher).
Resumen conceptual:

### Nodos principales

| Label             | Clave única        | Descripción |
|-------------------|--------------------|-------------|
| `Persona`         | `cuil`             | Persona física (CUIL/DNI). En modo público el documento va enmascarado. |
| `Empresa`         | `cuit`             | Persona jurídica. Razón social, CUIT, estado AFIP, actividad (CLAE). |
| `Funcionario`     | `funcionario_id`   | Rol institucional de una `Persona` en el Estado. |
| `Organismo`       | `organismo_id`     | Reparticiones del Estado (ministerios, municipios, entes). |
| `Contrato`        | `contrato_id`      | Orden de compra / contrato (COMPR.AR, CONTRAT.AR, provinciales). |
| `Licitacion`      | `licitacion_id`    | Proceso licitatorio (proceso de compra). |
| `Cargo`           | `cargo_id`         | Puesto público con fecha de alta/baja. |
| `Partido`         | `partido_id`       | Partido o alianza electoral. |
| `Candidatura`     | `candidatura_id`   | Postulación de una persona a un cargo electivo. |
| `AporteCampania`  | `aporte_id`        | Aporte de campaña (CNE). |
| `DeclaracionJurada` | `ddjj_id`        | DDJJ patrimonial integral (Oficina Anticorrupción). |
| `BienDeclarado`   | `bien_id`          | Ítem patrimonial dentro de una DDJJ. |
| `Sancion`         | `sancion_id`       | Inhabilitación / sanción (registro de proveedores, BORA). |
| `ActoBoletin`     | `acto_id`          | Acto administrativo publicado en el Boletín Oficial. |
| `CausaJudicial`   | `causa_id`         | Causa o sentencia (datos abiertos de Justicia). |
| `Domicilio`       | `domicilio_id`     | Domicilio normalizado vía API Georef. |
| `FuenteDocumento` | `doc_id`           | Trazabilidad: URL, hash, fecha de captura. |
| `CorridaIngesta`  | `corrida_id`       | Auditoría de cada ejecución de ETL (idempotencia). |

### Relaciones principales

```
(:Persona)-[:ES_FUNCIONARIO]->(:Funcionario)
(:Funcionario)-[:OCUPA {desde,hasta}]->(:Cargo)-[:EN]->(:Organismo)
(:Persona)-[:SOCIO_DE {pct,rol,desde,hasta}]->(:Empresa)
(:Persona)-[:APODERADO_DE]->(:Empresa)
(:Persona)-[:REPRESENTA_LEGAL]->(:Empresa)
(:Empresa)-[:ADJUDICATARIA_DE]->(:Contrato)
(:Contrato)-[:DERIVA_DE]->(:Licitacion)
(:Organismo)-[:CONVOCA]->(:Licitacion)
(:Organismo)-[:CONTRATA]->(:Contrato)
(:Persona)-[:PRESENTO]->(:DeclaracionJurada)
(:DeclaracionJurada)-[:DECLARA]->(:BienDeclarado)
(:Persona)-[:CANDIDATA_EN]->(:Candidatura)-[:POR]->(:Partido)
(:Candidatura)-[:POSTULA_A]->(:Cargo)
(:Persona|:Empresa)-[:APORTO {monto,fecha}]->(:Partido)
(:Empresa|:Persona)-[:SANCIONADA_POR]->(:Sancion)
(:Persona)-[:FAMILIAR_DE {vinculo}]->(:Persona)
(:Empresa)-[:TIENE_DOMICILIO]->(:Domicilio)
(:Persona)-[:TIENE_DOMICILIO]->(:Domicilio)
(n)-[:SEGUN_FUENTE]->(:FuenteDocumento)   // toda arista material es citable
(n)-[:INGESTADO_EN]->(:CorridaIngesta)
```

**Principio de trazabilidad:** ningún nodo o arista material existe sin al
menos un `:SEGUN_FUENTE` hacia una `FuenteDocumento`. Esto hace cada señal
auditable y reproducible.

**Resolución temporal:** las aristas con vigencia (`SOCIO_DE`, `OCUPA`,
`ADJUDICATARIA_DE`) llevan `desde`/`hasta`. Las reglas de conflicto de
interés exigen *solapamiento temporal* — clave para evitar falsos positivos.

---

## 3. Datasets prioritarios

Catálogo detallado, frecuencia de actualización y método de obtención en
[`datasets-ar.md`](datasets-ar.md). Resumen:

| Fuente | Qué aporta al grafo | Acceso | Frecuencia |
|--------|--------------------|--------|-----------|
| **datos.gob.ar** (CKAN) | Catálogo federal; APIs y CSV de cientos de datasets | API CKAN REST | Variable |
| **COMPR.AR** | Compras y contrataciones nacionales (bienes/servicios) | Portal + datasets en datos.gob.ar | Mensual |
| **CONTRAT.AR** | Obra pública nacional | Portal + CSV | Mensual |
| **DDJJ Patrimoniales** (Oficina Anticorrupción) | Patrimonio de funcionarios | Solicitud / datasets publicados | Anual |
| **AFIP / ARCA** | Padrón CUIT, estado administrativo, constancia de inscripción, actividad (CLAE) | API REST (constancia) / padrones | Diaria/Mensual |
| **Boletín Oficial (BORA)** | Designaciones, contrataciones, sociedades, sanciones | API BORA / scraping estructurado | Diaria |
| **Cámara Nacional Electoral** | Candidaturas, padrón de afiliados, aportes de campaña | Datasets CNE / datos.gob.ar | Por elección |
| **Presupuesto Abierto** | Crédito, devengado, pagado por programa/jurisdicción | API Presupuesto Abierto | Mensual |
| **API Georef** | Normalización de provincias, departamentos, municipios, calles, geocoding | API REST pública | Estable |
| **Datos de Justicia** (Min. Justicia / CSJN datos abiertos) | Causas, sentencias, registro de deudores alimentarios | Datasets / API | Variable |
| **Portal de Transparencia** | Audiencias, viajes, regalos, registro de obsequios | Datasets | Mensual |
| **Provinciales/Municipales** | Compras y boletines subnacionales (CABA, PBA, Córdoba, Santa Fe, Mendoza...) | Portales por jurisdicción | Variable |

Cada fuente se registra en `etl/src/aracc_etl/sources.yml` con: `source_id`,
URL, licencia, formato, cadencia y estado
(`loaded` / `partial` / `stale` / `blocked` / `not_built`).

---

## 4. Código base del ETL

Estructura en [`aracc/etl/`](../../aracc/etl/). El patrón es el de `br-acc`,
endurecido con scheduling Prefect:

- **`base.py`** — `Pipeline` abstracto con `extract()` / `transform()` /
  `load()` y un `run()` que registra cada corrida como nodo `CorridaIngesta`
  (idempotencia y auditoría). Incluido en este repo.
- **`loader.py`** — `Neo4jBatchLoader`: escrituras en lote vía `UNWIND` +
  `MERGE` (idempotente) con reintentos ante `TransientError`.
- **`runner.py`** — CLI `aracc-etl run <source> [--limit] [--since]`.
- **`flows.py`** — flujos Prefect: cada pipeline es una `@task`; los
  schedules viven en `deployments` (p. ej. BORA diario, COMPR.AR mensual).
- **`sources.yml`** — registro declarativo único de fuentes.
- **`pipelines/`** — un módulo por fuente. Incluidos como referencia:
  `datos_gob_ar.py`, `comprar.py`, `declaraciones_juradas.py`.

Idempotencia garantizada por: claves naturales estables (CUIT/CUIL) + `MERGE`
+ `source_hash` por registro (re-ejecutar no duplica ni corrompe).

---

## 5. Queries Cypher de detección

Conjunto completo y comentado en
[`aracc/queries/deteccion.cypher`](../../aracc/queries/deteccion.cypher).
Cubre las 6 familias de reglas pedidas:

1. **Enriquecimiento patrimonial** — salto de patrimonio en DDJJ
   consecutivas correlacionado con contratos ganados por empresas vinculadas.
2. **Sobreprecios / adjudicaciones directas repetidas** — contratación
   directa recurrente del mismo organismo al mismo proveedor; ítems por
   encima del percentil de precio de mercado.
3. **Empresas con mismo apoderado/domicilio** — clústeres de empresas que
   comparten domicilio o representante legal y compiten en la misma licitación.
4. **Conflictos de interés** — funcionario socio de una empresa que contrata
   con su propio organismo, con solapamiento temporal.
5. **Puerta giratoria** — funcionario que pasa al sector privado a una
   empresa que contrata con el Estado (revolving door).
6. **Inconsistencias en aportes electorales** — aportantes que superan
   topes, empresas proveedoras del Estado que aportan, aportes incompatibles
   con la capacidad patrimonial declarada.

---

## 6. Roadmap

Detalle por fase, hitos y criterios de salida en
[`roadmap.md`](roadmap.md).

- **Fase 0 — Fundación (semanas 1-4):** fork, renombre, esquema Neo4j AR,
  stack Docker, transforms de CUIT/CUIL, datos.gob.ar + Georef.
- **Fase 1 — MVP (meses 2-4):** COMPR.AR, BORA, DDJJ, padrón AFIP;
  búsqueda + explorador de grafo + 6 reglas de detección base; API pública.
- **Fase 2 — Versión 1.0 (meses 5-9):** CONTRAT.AR, CNE (candidatos/aportes),
  Presupuesto Abierto, Justicia; resolución de entidades probabilística;
  GraphQL; 2-3 provincias; reportes de investigación reproducibles.
- **Fase 3 — Avanzado con IA (meses 10+):** Neo4j GDS (detección de
  comunidades, centralidad), scoring de riesgo con ML supervisado sobre
  casos conocidos, extracción NLP del Boletín Oficial, alertas en tiempo real.

---

## 7. Consideraciones legales

Documento completo en [`legal/marco-legal-ar.md`](legal/marco-legal-ar.md).
Principios:

- **Solo datos públicos.** `ar-acc` únicamente ingiere información ya
  publicada oficialmente bajo la **Ley 27.275 de Acceso a la Información
  Pública** y el principio de transparencia activa. No se hace scraping de
  fuentes privadas ni se elude ningún control de acceso.
- **Ley 25.326 de Protección de los Datos Personales.** Aunque los datos de
  funcionarios en ejercicio tienen interés público preponderante, se aplica
  *minimización*: en el **modo público** los identificadores (CUIT/CUIL/DNI)
  se exhiben enmascarados (`20-XX·XXX·X45-3`); el dato completo solo en
  despliegues internos autenticados. Existe un canal de
  **rectificación/supresión** (issue template `data_correction`).
- **Disclaimer fuerte.** Toda vista, export y respuesta de API incluye:
  *"ar-acc agrega datos públicos y muestra conexiones; NO afirma la comisión
  de delito alguno. Las señales son hipótesis a verificar contra la fuente
  oficial citada. La presunción de inocencia es inviolable."*
- **Licencia AGPL-3.0** (heredada de `br-acc`): garantiza que toda mejora
  desplegada como servicio vuelva a la comunidad.
- **Trazabilidad como defensa legal:** cada afirmación enlaza a su
  `FuenteDocumento` (URL + hash + fecha), de modo que el proyecto reproduce
  el dato oficial, no lo origina.

---

## 8. Atraer contribuidores

- **Documentación bilingüe** (es-AR / en) y `ARQUITECTURA.md` como esta.
- **`CONTRIBUTING.md`** con setup de un comando: `make bootstrap-demo`
  levanta el stack con un grafo sintético — onboarding en < 10 minutos.
- **Issues etiquetados** `good-first-issue` / `help-wanted` / `pipeline:<fuente>`:
  agregar una fuente provincial es una tarea acotada e ideal para empezar.
- **Plantillas de issue** para nuevas fuentes, corrección de datos y
  solicitudes de privacidad.
- **`datasets-ar.md` como tablero abierto:** cada fila `not_built` es una
  invitación explícita a contribuir un pipeline.
- **Tests y CI desde el día 1:** fixtures por pipeline; un PR con pipeline
  nuevo + test + fila en `sources.yml` se mergea con confianza.
- **Comunidad:** Discord/Matrix, llamada mensual de contribuidores, y
  reconocimiento en `CHANGELOG.md` y release notes.
- **Buenas causas concretas:** "datatones" con periodistas de datos y
  ONGs (Poder Ciudadano, ACIJ, Directorio Legislativo) sobre casos reales.
