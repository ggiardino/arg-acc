"""Dashboard local de ar-acc (Streamlit).

Permite cambiar el proveedor de IA en caliente, ver métricas del grafo de
Neo4j en tiempo real y chatear con el agente de investigación.

Uso:
    streamlit run web/app_streamlit.py
"""

from __future__ import annotations

import pathlib
import sys

# Agrega la raíz del proyecto al path para resolver `agent` y `config`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402
from neo4j.exceptions import Neo4jError  # noqa: E402

from agent import query_corruption_graph  # noqa: E402
from config.settings import settings  # noqa: E402


st.set_page_config(page_title="ar-acc · Investigación de corrupción",
                   page_icon="🔎", layout="wide")


# --------------------------------------------------------------------------
# Acceso a Neo4j para las métricas
# --------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_driver():
    """Driver de Neo4j cacheado durante la sesión de Streamlit."""
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def get_metrics() -> dict[str, int]:
    """Cuenta nodos, relaciones y entidades clave directamente en Neo4j."""
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        return {
            "nodos": session.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            "relaciones": session.run(
                "MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
            "funcionarios": session.run(
                "MATCH (n:Funcionario) RETURN count(n) AS c").single()["c"],
            "empresas": session.run(
                "MATCH (n:Empresa) RETURN count(n) AS c").single()["c"],
        }


# --------------------------------------------------------------------------
# Barra lateral — configuración dinámica del proveedor de IA
# --------------------------------------------------------------------------

st.sidebar.title("⚙️ Configuración")

proveedores = ["openai", "groq", "anthropic"]
provider_default = (
    proveedores.index(settings.llm_provider)
    if settings.llm_provider in proveedores else 1
)
provider = st.sidebar.selectbox(
    "Proveedor de IA",
    proveedores,
    index=provider_default,
    format_func=str.capitalize,
)

clave_en_env = bool(settings.api_key_for(provider))
if clave_en_env:
    st.sidebar.success(f"API Key de {provider.capitalize()} cargada desde .env")
    api_key_input = ""
else:
    st.sidebar.warning(f"No hay API Key de {provider.capitalize()} en el .env")

api_key_input = st.sidebar.text_input(
    f"API Key de {provider.capitalize()} (opcional)",
    type="password",
    help="Si la dejás vacía se usa la del archivo .env.",
)
api_key = api_key_input.strip() or None

st.sidebar.caption(f"Modelo: `{settings.model_for(provider)}`")
st.sidebar.divider()
st.sidebar.caption(f"Neo4j: `{settings.neo4j_uri}`")


# --------------------------------------------------------------------------
# Encabezado y métricas del grafo
# --------------------------------------------------------------------------

st.title("🔎 ar-acc — Investigación de corrupción")
st.caption("Réplica argentina y ligera del framework acc/bro de OCCRP. "
           "Consultá el grafo de Neo4j en lenguaje natural.")

try:
    metrics = get_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nodos totales", metrics["nodos"])
    c2.metric("Relaciones totales", metrics["relaciones"])
    c3.metric("Funcionarios", metrics["funcionarios"])
    c4.metric("Empresas", metrics["empresas"])
    if metrics["nodos"] == 0:
        st.warning("El grafo está vacío. Ejecutá la ingesta: "
                   "`python -m pipelines.import_to_neo4j`")
except (Neo4jError, OSError, ValueError) as exc:
    st.error(f"No se pudo conectar a Neo4j ({settings.neo4j_uri}). "
             f"Revisá el .env y que la base esté activa.\n\nDetalle: {exc}")

st.divider()


# --------------------------------------------------------------------------
# Chat con el agente
# --------------------------------------------------------------------------

st.subheader("💬 Consultá al agente")

with st.expander("Ejemplos de preguntas de auditoría"):
    st.markdown(
        "- ¿Qué funcionarios tienen un patrimonio desproporcionado respecto "
        "de sus ingresos y a qué destinos del exterior viajaron?\n"
        "- ¿Qué empresas ganaron más de un contrato del Estado y cuál es el "
        "monto total adjudicado a cada una?\n"
        "- ¿Qué funcionarios viajaron a paraísos fiscales como las Islas "
        "Caimán o Andorra y cuál es su cargo?"
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

pregunta = st.chat_input("Escribí tu pregunta sobre el grafo de corrupción...")

if pregunta:
    st.session_state.messages.append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando el grafo..."):
            respuesta = query_corruption_graph(
                pregunta, provider=provider, api_key=api_key)
        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
