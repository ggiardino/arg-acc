"""Resolución de entidades para ar-acc.

Módulo básico de record linkage: decide cuándo dos nodos `Persona` o
`Empresa` provenientes de fuentes distintas son, probablemente, la misma
entidad del mundo real.

Estrategia (sin dependencias externas):
  1. Normalización de nombres y razones sociales.
  2. Bloqueo (blocking) para evitar la comparación O(n²).
  3. Similitud por token + secuencia de caracteres.
  4. Confianza ponderada con señales fuertes (CUIT/domicilio compartido).

El resultado son *candidatos* de match, no fusiones automáticas: se
materializan como relaciones `POSIBLE_MISMO_QUE` para revisión humana.
"""

from aracc_etl.entity_resolution.linker import (
    CandidatoMatch,
    EntityResolver,
    cypher_posible_mismo_que,
)
from aracc_etl.entity_resolution.matcher import clave_bloqueo, nivel_confianza, similitud
from aracc_etl.entity_resolution.normalize import (
    normalizar_nombre,
    normalizar_razon_social,
    tokens,
)

__all__ = [
    "CandidatoMatch",
    "EntityResolver",
    "clave_bloqueo",
    "cypher_posible_mismo_que",
    "nivel_confianza",
    "normalizar_nombre",
    "normalizar_razon_social",
    "similitud",
    "tokens",
]
