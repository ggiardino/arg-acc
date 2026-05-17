"""Similitud, bloqueo y confianza para el record linkage.

Sin dependencias externas: usa `difflib` de la stdlib para la similitud
a nivel de caracteres y Jaccard para la similitud a nivel de tokens.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from aracc_etl.entity_resolution.normalize import (
    normalizar_nombre,
    normalizar_razon_social,
    tokens,
)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similitud(nombre_a: str, nombre_b: str, *, empresa: bool = False) -> float:
    """Similitud entre dos nombres en [0, 1].

    Combina dos señales:
      - Jaccard sobre tokens (robusto al orden y a tokens faltantes).
      - Ratio de `SequenceMatcher` sobre la forma canónica (robusto a
        errores de tipeo y variantes ortográficas).
    Se pondera más la de tokens, que tolera mejor las abreviaturas.
    """
    normalizar = normalizar_razon_social if empresa else normalizar_nombre
    canon_a, canon_b = normalizar(nombre_a), normalizar(nombre_b)
    if not canon_a or not canon_b:
        return 0.0
    if canon_a == canon_b:
        return 1.0
    jac = _jaccard(tokens(nombre_a), tokens(nombre_b))
    seq = SequenceMatcher(None, canon_a, canon_b).ratio()
    return round(0.6 * jac + 0.4 * seq, 4)


def clave_bloqueo(nombre: str, *, empresa: bool = False) -> str:
    """Clave de bloqueo: agrupa candidatos comparables sin comparar todo.

    Usa el prefijo del primer token de la forma canónica. Solo se
    comparan entre sí los registros que comparten clave -> O(n²) por
    bloque en lugar de sobre el universo completo.
    """
    normalizar = normalizar_razon_social if empresa else normalizar_nombre
    canon = normalizar(nombre)
    if not canon:
        return "_"
    primer = canon.split()[0]
    return primer[:4]


def nivel_confianza(
    score: float,
    *,
    cuit_compartido: bool = False,
    domicilio_compartido: bool = False,
) -> str:
    """Traduce un score y señales fuertes a un nivel de confianza.

    Un CUIT/CUIL compartido es identidad por definición -> 'alta'.
    Un domicilio compartido refuerza una coincidencia de nombre.
    """
    if cuit_compartido:
        return "alta"
    if score >= 0.92 or (score >= 0.80 and domicilio_compartido):
        return "alta"
    if score >= 0.80:
        return "media"
    if score >= 0.65:
        return "baja"
    return "descartado"
