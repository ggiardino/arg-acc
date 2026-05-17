"""Capa de IA de ar-acc.

Expone `query_corruption_graph(question)` que traduce una pregunta en lenguaje
cotidiano a una consulta Cypher, la ejecuta sobre el grafo de Neo4j y devuelve
una respuesta analítica en español rioplatense.

Se apoya en `GraphCypherQAChain` de LangChain y soporta tres proveedores de
IA intercambiables: OpenAI, Groq y Anthropic.
"""

from __future__ import annotations

import os
import pathlib
import sys

# Garantiza que la raíz del proyecto esté en el path (para `config`).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from langchain_core.prompts import PromptTemplate  # noqa: E402

from config.settings import settings  # noqa: E402

try:  # API moderna recomendada.
    from langchain_neo4j import GraphCypherQAChain, Neo4jGraph  # noqa: E402
except ImportError:  # Fallback a langchain-community.
    from langchain.chains import GraphCypherQAChain  # noqa: E402
    from langchain_community.graphs import Neo4jGraph  # noqa: E402


# --------------------------------------------------------------------------
# Prompts en español argentino
# --------------------------------------------------------------------------

CYPHER_GENERATION_TEMPLATE = """Sos un experto en Neo4j y en investigación \
periodística de corrupción en la Argentina. Tu tarea es convertir una pregunta \
escrita en lenguaje cotidiano en una única consulta Cypher válida.

Esquema real del grafo (usalo como única fuente de verdad):
{schema}

Glosario para mapear el lenguaje coloquial al grafo:
- "empleados públicos", "funcionarios", "ministros", "secretarios", "intendentes"
  -> nodo (:Funcionario)
- "sueldo", "salario", "lo que cobran", "lo que declaran ganar"
  -> propiedad `ingresos` de (:Funcionario)
- "patrimonio", "bienes", "fortuna", "lo que tienen", "riqueza"
  -> propiedad `patrimonio` de (:Funcionario)
- "cargo", "puesto", "función" -> propiedad `cargo` de (:Funcionario)
- "viajes al exterior", "vuelos afuera", "se fueron de viaje", "viajaron"
  -> relación (:Funcionario)-[:VIAJO_A]->(:Destino)
- "paraíso fiscal", "guarida fiscal", "offshore"
  -> nodos (:Destino) cuyo `pais` esté en ['Islas Caimán', 'Andorra', 'Panamá']
- "empresas", "proveedores", "contratistas" -> nodo (:Empresa)
- "obras", "contratos del Estado", "licitaciones", "adjudicaciones"
  -> nodo (:Licitacion)
- "ganó una obra", "se quedó con el contrato", "fue adjudicada"
  -> relación (:Empresa)-[:GANO_CONTRATO]->(:Licitacion)

Reglas estrictas:
- Devolvé EXCLUSIVAMENTE la consulta Cypher, sin explicaciones ni backticks.
- Está PROHIBIDO usar cláusulas que modifiquen datos (CREATE, MERGE, SET,
  DELETE, REMOVE, DROP). La consulta debe ser de solo lectura.
- Usá los nombres de etiquetas, relaciones y propiedades exactamente como
  figuran en el esquema.
- Cuando compares texto, usá `toLower()` para que no dependa de mayúsculas.
- Si la pregunta pide "desproporción" entre patrimonio e ingresos, calculá la
  razón `f.patrimonio * 1.0 / f.ingresos`.

Pregunta: {question}
Cypher:"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_GENERATION_TEMPLATE,
)

QA_TEMPLATE = """Sos un analista de transparencia y anticorrupción argentino. \
Tenés que responder la pregunta del usuario en español rioplatense, de forma \
clara, profesional y concreta.

Basate ÚNICAMENTE en la información provista abajo, que proviene de una \
consulta al grafo. Si la información está vacía, aclará explícitamente que no \
hay datos suficientes para responder y no inventes nada.

Cuando los datos lo permitan, señalá indicios de riesgo de corrupción (por \
ejemplo: un patrimonio desproporcionado frente a los ingresos declarados, \
viajes recurrentes a paraísos fiscales, o concentración de contratos en una \
misma empresa). Presentá las cifras en pesos de forma legible.

Información obtenida del grafo:
{context}

Pregunta: {question}
Respuesta analítica:"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=QA_TEMPLATE,
)


# --------------------------------------------------------------------------
# Inicialización del LLM según el proveedor
# --------------------------------------------------------------------------

def get_llm(provider: str | None = None, api_key: str | None = None):
    """Devuelve el modelo de chat correspondiente al proveedor seleccionado.

    `provider` y `api_key` permiten sobrescribir dinámicamente lo definido en
    el `.env` (por ejemplo, desde el dashboard o el endpoint serverless).
    """
    provider = (provider or settings.llm_provider).lower()

    if provider == "openai":
        key = api_key or settings.openai_api_key
        _require_key(key, "OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = key
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.openai_model, temperature=0)

    if provider == "groq":
        key = api_key or settings.groq_api_key
        _require_key(key, "GROQ_API_KEY")
        os.environ["GROQ_API_KEY"] = key
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.groq_model, temperature=0)

    if provider == "anthropic":
        key = api_key or settings.anthropic_api_key
        _require_key(key, "ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = key
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.anthropic_model, temperature=0)

    raise ValueError(
        f"Proveedor de IA no soportado: '{provider}'. "
        f"Opciones válidas: openai, groq, anthropic."
    )


def _require_key(key: str, env_name: str) -> None:
    if not key:
        raise ValueError(
            f"Falta la API Key '{env_name}'. Cargala en el archivo .env "
            f"o pegala en la barra lateral del dashboard."
        )


# --------------------------------------------------------------------------
# Construcción de la cadena GraphCypherQAChain
# --------------------------------------------------------------------------

def get_graph() -> Neo4jGraph:
    """Crea la conexión LangChain al grafo de Neo4j."""
    return Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )


def build_chain(provider: str | None = None, api_key: str | None = None) -> GraphCypherQAChain:
    """Arma la cadena de pregunta-respuesta sobre el grafo."""
    llm = get_llm(provider, api_key)
    graph = get_graph()
    return GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=CYPHER_GENERATION_PROMPT,
        qa_prompt=QA_PROMPT,
        verbose=True,
        validate_cypher=True,
        top_k=25,
        allow_dangerous_requests=True,
    )


def query_corruption_graph(
    question: str,
    provider: str | None = None,
    api_key: str | None = None,
) -> str:
    """Responde una pregunta de auditoría consultando el grafo de corrupción.

    Devuelve siempre un string: la respuesta analítica o un mensaje de error
    legible para el usuario final.
    """
    question = (question or "").strip()
    if not question:
        return "Escribí una pregunta para consultar el grafo."

    try:
        chain = build_chain(provider, api_key)
        result = chain.invoke({"query": question})
        answer = (result.get("result") or "").strip()
        return answer or "No encontré información en el grafo para esa consulta."
    except Exception as exc:  # noqa: BLE001
        return f"No se pudo procesar la consulta. Detalle: {exc}"


if __name__ == "__main__":
    pregunta = " ".join(sys.argv[1:]) or (
        "¿Qué funcionarios tienen un patrimonio desproporcionado "
        "respecto de sus ingresos?"
    )
    print(query_corruption_graph(pregunta))
