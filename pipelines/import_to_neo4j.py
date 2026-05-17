"""Pipeline de ingesta de ar-acc.

Limpia por completo el grafo de Neo4j e inyecta un dataset simulado con
contexto de corrupción argentina (funcionarios, empresas, destinos y
licitaciones) para poder probar el agente de IA de inmediato.

Uso:
    python -m pipelines.import_to_neo4j
"""

from __future__ import annotations

import pathlib
import sys

# Permite ejecutar el script directamente agregando la raíz del proyecto
# al path de importación (para resolver `config`).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from neo4j import GraphDatabase  # noqa: E402

from config.settings import settings  # noqa: E402


# --------------------------------------------------------------------------
# Dataset simulado — contexto de corrupción argentina (datos ficticios)
# --------------------------------------------------------------------------

FUNCIONARIOS = [
    {"id": "F1", "nombre": "Ricardo Olmedo", "cargo": "Ministro de Infraestructura",
     "ingresos": 7_800_000, "patrimonio": 920_000_000},
    {"id": "F2", "nombre": "Mónica Sandoval", "cargo": "Secretaria de Obras Públicas",
     "ingresos": 5_400_000, "patrimonio": 210_000_000},
    {"id": "F3", "nombre": "Hernán Vázquez", "cargo": "Director Nacional de Compras",
     "ingresos": 4_900_000, "patrimonio": 88_000_000},
    {"id": "F4", "nombre": "Lucía Ferreyra", "cargo": "Subsecretaria de Transporte",
     "ingresos": 5_100_000, "patrimonio": 19_000_000},
    {"id": "F5", "nombre": "Gustavo Peralta", "cargo": "Intendente Municipal",
     "ingresos": 4_200_000, "patrimonio": 305_000_000},
]

DESTINOS = [
    {"id": "D1", "nombre": "Miami", "pais": "Estados Unidos"},
    {"id": "D2", "nombre": "Punta del Este", "pais": "Uruguay"},
    {"id": "D3", "nombre": "George Town", "pais": "Islas Caimán"},
    {"id": "D4", "nombre": "Andorra la Vella", "pais": "Andorra"},
    {"id": "D5", "nombre": "Madrid", "pais": "España"},
]

EMPRESAS = [
    {"id": "E1", "razon_social": "Constructora del Litoral SA", "cuit": "30-71234567-8"},
    {"id": "E2", "razon_social": "Vialidad Andina SRL", "cuit": "30-70987654-3"},
    {"id": "E3", "razon_social": "Insumos Patagónicos SA", "cuit": "33-69876543-9"},
    {"id": "E4", "razon_social": "Servicios Integrales del Plata SA", "cuit": "30-71555888-1"},
]

LICITACIONES = [
    {"id": "L1", "objeto": "Repavimentación Ruta Nacional 14", "monto": 5_400_000_000,
     "organismo": "Vialidad Nacional", "anio": 2022},
    {"id": "L2", "objeto": "Construcción Hospital Modular Norte", "monto": 2_100_000_000,
     "organismo": "Ministerio de Salud", "anio": 2023},
    {"id": "L3", "objeto": "Provisión de luminarias LED", "monto": 780_000_000,
     "organismo": "Municipalidad", "anio": 2023},
    {"id": "L4", "objeto": "Mantenimiento de edificios públicos", "monto": 320_000_000,
     "organismo": "Ministerio de Infraestructura", "anio": 2024},
]

# Relación (:Funcionario)-[:VIAJO_A]->(:Destino)
VIAJES = [
    {"funcionario": "F1", "destino": "D3", "fecha": "2023-03-12", "costo": 18_500_000},
    {"funcionario": "F1", "destino": "D4", "fecha": "2023-09-28", "costo": 21_000_000},
    {"funcionario": "F1", "destino": "D1", "fecha": "2024-01-15", "costo": 9_800_000},
    {"funcionario": "F2", "destino": "D2", "fecha": "2023-12-20", "costo": 3_400_000},
    {"funcionario": "F2", "destino": "D1", "fecha": "2024-02-10", "costo": 8_700_000},
    {"funcionario": "F3", "destino": "D4", "fecha": "2023-07-05", "costo": 16_200_000},
    {"funcionario": "F3", "destino": "D5", "fecha": "2024-03-22", "costo": 7_100_000},
    {"funcionario": "F5", "destino": "D3", "fecha": "2023-11-09", "costo": 19_700_000},
    {"funcionario": "F5", "destino": "D2", "fecha": "2024-01-30", "costo": 4_200_000},
]

# Relación (:Empresa)-[:GANO_CONTRATO]->(:Licitacion)
CONTRATOS = [
    {"empresa": "E1", "licitacion": "L1", "fecha": "2022-08-05", "monto_adjudicado": 5_400_000_000},
    {"empresa": "E1", "licitacion": "L2", "fecha": "2023-04-18", "monto_adjudicado": 2_100_000_000},
    {"empresa": "E2", "licitacion": "L4", "fecha": "2024-02-27", "monto_adjudicado": 320_000_000},
    {"empresa": "E3", "licitacion": "L3", "fecha": "2023-10-11", "monto_adjudicado": 780_000_000},
]


def importar() -> None:
    """Conecta a Neo4j, limpia el grafo e inyecta el dataset simulado."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        driver.close()
        raise SystemExit(
            f"[ar-acc] No se pudo conectar a Neo4j en {settings.neo4j_uri}.\n"
            f"Verificá que la base esté activa y las credenciales del .env.\n"
            f"Detalle: {exc}"
        )

    with driver.session(database=settings.neo4j_database) as session:
        print("[ar-acc] Limpiando el grafo...")
        session.run("MATCH (n) DETACH DELETE n")

        print("[ar-acc] Creando nodos :Funcionario ...")
        session.run("UNWIND $rows AS r CREATE (f:Funcionario) SET f = r", rows=FUNCIONARIOS)

        print("[ar-acc] Creando nodos :Destino ...")
        session.run("UNWIND $rows AS r CREATE (d:Destino) SET d = r", rows=DESTINOS)

        print("[ar-acc] Creando nodos :Empresa ...")
        session.run("UNWIND $rows AS r CREATE (e:Empresa) SET e = r", rows=EMPRESAS)

        print("[ar-acc] Creando nodos :Licitacion ...")
        session.run("UNWIND $rows AS r CREATE (l:Licitacion) SET l = r", rows=LICITACIONES)

        print("[ar-acc] Creando relaciones :VIAJO_A ...")
        session.run(
            """
            UNWIND $rows AS r
            MATCH (f:Funcionario {id: r.funcionario})
            MATCH (d:Destino {id: r.destino})
            CREATE (f)-[:VIAJO_A {fecha: r.fecha, costo: r.costo}]->(d)
            """,
            rows=VIAJES,
        )

        print("[ar-acc] Creando relaciones :GANO_CONTRATO ...")
        session.run(
            """
            UNWIND $rows AS r
            MATCH (e:Empresa {id: r.empresa})
            MATCH (l:Licitacion {id: r.licitacion})
            CREATE (e)-[:GANO_CONTRATO {fecha: r.fecha,
                                        monto_adjudicado: r.monto_adjudicado}]->(l)
            """,
            rows=CONTRATOS,
        )

        nodos = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    driver.close()

    print("-" * 60)
    print(f"[ar-acc] Ingesta finalizada con éxito.")
    print(f"[ar-acc] Nodos creados:      {nodos}")
    print(f"[ar-acc] Relaciones creadas: {rels}")
    print("-" * 60)


if __name__ == "__main__":
    importar()
