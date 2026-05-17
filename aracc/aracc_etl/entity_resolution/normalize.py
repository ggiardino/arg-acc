"""Normalización de nombres de personas y razones sociales.

La normalización es el cimiento del record linkage: dos nombres que
representan a la misma entidad deben converger a la misma forma canónica
(o lo más cerca posible) antes de compararlos.
"""

from __future__ import annotations

import re
import unicodedata

# Sufijos societarios argentinos (y abreviaturas). Se eliminan de las
# razones sociales: no aportan a la identidad de la empresa.
_SUFIJOS_SOCIETARIOS = {
    "SA", "SRL", "SAS", "SACI", "SACIF", "SACIFIA", "SCA", "SCS",
    "SAU", "SE", "SH", "SCEI", "LTDA", "SAICF", "SAIC", "SAYC",
    "COOP", "COOPERATIVA", "ASOCIACION", "FUNDACION", "UTE",
}

# Partículas que no aportan a la identidad de una persona.
_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "DA", "DI"}

_NO_ALFANUM = re.compile(r"[^A-Z0-9 ]+")
_ESPACIOS = re.compile(r"\s+")


def quitar_acentos(texto: str) -> str:
    """Elimina tildes y diacríticos (José -> JOSE)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _limpiar(texto: str) -> str:
    """Mayúsculas, sin acentos, sin puntuación, espacios colapsados.

    Los puntos se eliminan sin dejar espacio para que las siglas
    societarias colapsen ('S.A.' -> 'SA', 'S.R.L.' -> 'SRL').
    """
    t = quitar_acentos(texto or "").upper()
    t = t.replace("&", " Y ").replace(".", "")
    t = _NO_ALFANUM.sub(" ", t)
    return _ESPACIOS.sub(" ", t).strip()


def normalizar_nombre(nombre: str) -> str:
    """Forma canónica del nombre de una persona.

    Ordena los tokens alfabéticamente para que 'GOMEZ, JUAN' y
    'JUAN GOMEZ' converjan, e ignora partículas ('de', 'la').
    """
    base = _limpiar(nombre)
    partes = [p for p in base.split() if p not in _PARTICULAS]
    return " ".join(sorted(partes))


def normalizar_razon_social(razon: str) -> str:
    """Forma canónica de una razón social, sin sufijos societarios."""
    base = _limpiar(razon)
    partes = [p for p in base.split() if p not in _SUFIJOS_SOCIETARIOS]
    return " ".join(partes)


def tokens(texto: str) -> set[str]:
    """Conjunto de tokens significativos de un texto ya normalizado."""
    return {p for p in _limpiar(texto).split() if p not in _PARTICULAS}
