# ar-acc — Argentina Transparency Graph (WTG-AR)

Adaptación argentina del proyecto brasileño
[`br-acc`](https://github.com/brunoclz/br-acc): un **grafo de conocimiento
abierto** que cruza las bases de datos públicas de Argentina para
detectar incompatibilidades patrimoniales, redes de contratistas,
sobreprecios, conflictos de interés y señales de riesgo en los tres
niveles del Estado (nacional, provincial y municipal).

> `ar-acc` **no interpreta ni acusa**: normaliza datos ya públicos pero
> dispersos y expone conexiones. Cada señal es una hipótesis verificable,
> con trazabilidad completa a la fuente oficial. Rige la presunción de
> inocencia.

## Contenido de este directorio (scaffold de la adaptación)

```
aracc/
├── docker-compose.yml         # Stack local: Neo4j + schema + seed + ETL
├── Dockerfile                 # Runtime del ETL
├── Makefile                   # Atajos: make demo / make test / ...
├── pyproject.toml             # Paquete aracc_etl + CLI `aracc-etl`
├── SETUP.md                   # Guía de setup local paso a paso
├── schema/
│   ├── init-neo4j.cypher      # Esquema del grafo: constraints + índices
│   └── seed-demo.cypher       # Grafo de demostración SINTÉTICO
├── queries/
│   ├── deteccion.cypher       # Queries de detección (parametrizadas)
│   └── demo-deteccion.cypher  # Idem, listas para correr sobre la demo
├── tests/                     # Tests (no requieren Neo4j)
└── aracc_etl/                 # Paquete Python instalable
    ├── base.py                # Clase Pipeline (extract/transform/load)
    ├── runner.py              # CLI `aracc-etl run <fuente>`
    ├── download.py            # Descarga resiliente + resolución CKAN
    ├── flows.py               # Flujos Prefect (scheduling)
    ├── sources.yml            # Registro declarativo de fuentes
    ├── transforms/            # Normalización CUIT/CUIL y montos AR
    ├── entity_resolution/     # Resolución de entidades (linkage)
    └── pipelines/             # Un módulo por fuente
        ├── datos_gob_ar.py
        ├── comprar.py
        └── declaraciones_juradas.py
```

Ver **[SETUP.md](SETUP.md)** para levantar el stack en minutos. Atajo:
`make demo` deja un grafo navegable con datos sintéticos.

## Documentación

- **[Arquitectura completa](../docs/ar-acc/ARQUITECTURA.md)** — los 8
  entregables: estructura, schema, datasets, ETL, queries, roadmap, marco
  legal y guía para contribuidores.
- [Catálogo de datasets](../docs/ar-acc/datasets-ar.md)
- [Roadmap (MVP → 1.0 → IA)](../docs/ar-acc/roadmap.md)
- [Marco legal argentino](../docs/ar-acc/legal/marco-legal-ar.md)

## Stack

Neo4j (grafo) · FastAPI + GraphQL (backend) · Prefect (ETL schedulable) ·
React/Vite (frontend) · Neo4j GDS + ML (analítica avanzada).

## Estado

Scaffold de la adaptación AR sobre la base `br-acc`. Ver el roadmap para
las fases. Las filas `not_built` en `sources.yml` son invitaciones
abiertas a contribuir.
