# ar-acc — atajos de desarrollo. Ejecutar desde el directorio aracc/.
.DEFAULT_GOAL := help
.PHONY: help up schema seed demo etl-ddjj down clean install test

help:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Levanta Neo4j en segundo plano
	docker compose up -d neo4j

schema:  ## Aplica el esquema del grafo (constraints + índices)
	docker compose run --rm schema-init

seed:  ## Carga el grafo de demostración SINTÉTICO
	docker compose run --rm seed-demo

demo: up schema seed  ## Setup completo: Neo4j + esquema + grafo de demo
	@echo ""
	@echo "  Listo. Abrí el Neo4j Browser en http://localhost:7474"
	@echo "  Probá las queries de detección en queries/deteccion.cypher"

etl-ddjj:  ## Corre el pipeline de Declaraciones Juradas (año 2023)
	docker compose run --rm etl run ddjj --anio 2023 --limit 500

down:  ## Detiene los servicios (conserva los datos)
	docker compose down

clean:  ## Detiene los servicios y BORRA el volumen de datos
	docker compose down -v

install:  ## Instala el paquete aracc_etl + dependencias de desarrollo
	pip install -e ".[dev]"

test:  ## Corre los tests (no requieren Neo4j)
	pytest -q
