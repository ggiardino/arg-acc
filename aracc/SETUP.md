# ar-acc — Setup local

Guía para levantar el grafo de `ar-acc` en tu máquina. Todo el stack
corre en Docker; no necesitás instalar Neo4j ni Python en el host.

## Requisitos

- Docker 24+ y Docker Compose v2.
- ~2 GB de RAM libres para el dev stack (más para el grafo completo).
- Opcional, para desarrollo sin Docker: Python 3.12+.

## 1. Configurar el entorno

```bash
cd aracc
cp .env.example .env
# Editá .env y poné una NEO4J_PASSWORD propia.
```

## 2. Levantar Neo4j

```bash
docker compose up -d neo4j
```

Esperá a que el healthcheck pase (`docker compose ps` debe mostrar
`healthy`). Luego abrí el navegador de Neo4j:

- Neo4j Browser: http://localhost:7474
  (usuario `neo4j`, contraseña la de tu `.env`)

## 3. Aplicar el esquema del grafo

Constraints e índices se aplican con un job de un solo uso e idempotente:

```bash
docker compose run --rm schema-init
```

Debe imprimir `Esquema ar-acc aplicado.`. Podés re-ejecutarlo sin riesgo
(todas las sentencias usan `IF NOT EXISTS`).

## 4. Ejecutar un pipeline ETL

El runtime del ETL es un contenedor on-demand (perfil `etl`):

```bash
# Listar los pipelines disponibles
docker compose run --rm etl list

# Indexar el catálogo de datos.gob.ar (descarga vía API CKAN)
docker compose run --rm etl run datos_gob_ar --limit 50

# Ingerir Declaraciones Juradas Patrimoniales (datos.jus.gob.ar)
docker compose run --rm etl run ddjj --anio 2023 --limit 500
```

Cada corrida deja un nodo `:CorridaIngesta` en el grafo con su estado y
métricas (auditoría e idempotencia).

## 5. Explorar el grafo

En el Neo4j Browser (http://localhost:7474):

```cypher
// ¿Qué se ingirió?
MATCH (c:CorridaIngesta) RETURN c ORDER BY c.inicio DESC;

// Funcionarios con más patrimonio declarado
MATCH (p:Persona)-[:PRESENTO]->(d:DeclaracionJurada)
RETURN p.nombre, d.anio, d.patrimonio_total
ORDER BY d.patrimonio_total DESC LIMIT 20;
```

Las queries de detección de riesgo están en
[`queries/deteccion.cypher`](queries/deteccion.cypher).

## Desarrollo sin Docker (opcional)

```bash
cd aracc
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # instala aracc_etl + pytest

export NEO4J_URI=bolt://localhost:7687
export NEO4J_PASSWORD=<tu-password>

aracc-etl list
aracc-etl run ddjj --anio 2023 --limit 500
pytest                           # corre los tests (no requieren Neo4j)
```

## Parar y limpiar

```bash
docker compose down              # detiene los servicios
docker compose down -v           # además borra el volumen de datos
```

## Problemas frecuentes

- **`schema-init` falla con "Connection refused":** Neo4j todavía no
  está `healthy`. Esperá unos segundos y reintentá.
- **Contraseña incorrecta:** si cambiaste `NEO4J_PASSWORD` después del
  primer arranque, el volumen conserva la anterior. Corré
  `docker compose down -v` para empezar de cero.
- **El ETL no encuentra datos:** los pipelines que leen archivos locales
  esperan los CSV en `./data/<fuente>/raw/`. Los pipelines con descarga
  propia (p. ej. `ddjj`) los bajan solos si hay conectividad.
