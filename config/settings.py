"""Configuración centralizada de ar-acc.

Lee las variables de entorno desde un archivo `.env` ubicado en la raíz del
proyecto usando `pydantic-settings`. Si una variable no está definida, se usa
el valor por defecto declarado en la clase `Settings`.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de conexión, claves de IA y selector de proveedor."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Conexión a Neo4j (Neo4j Desktop local o Neo4j Aura en la nube) ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"

    # --- API Keys de los proveedores de IA ---
    openai_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    # --- Selector dinámico de proveedor y modelo ---
    llm_provider: Literal["openai", "groq", "anthropic"] = "groq"
    openai_model: str = "gpt-4o-mini"
    groq_model: str = "llama-3.3-70b-versatile"
    anthropic_model: str = "claude-sonnet-4-6"

    def api_key_for(self, provider: str) -> str:
        """Devuelve la API Key configurada para el proveedor indicado."""
        return {
            "openai": self.openai_api_key,
            "groq": self.groq_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(provider.lower(), "")

    def model_for(self, provider: str) -> str:
        """Devuelve el nombre del modelo configurado para el proveedor."""
        return {
            "openai": self.openai_model,
            "groq": self.groq_model,
            "anthropic": self.anthropic_model,
        }.get(provider.lower(), self.groq_model)


# Instancia única reutilizable en todo el proyecto.
settings = Settings()
