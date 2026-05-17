"""Normalización de montos monetarios en formato argentino.

Argentina usa el punto como separador de miles y la coma como separador
decimal: '1.234.567,89'. Los datasets oficiales mezclan formatos, así
que se normaliza siempre a float.
"""

from __future__ import annotations

import re

_LIMPIEZA = re.compile(r"[^\d,.\-]")


def normalizar_monto(valor: str | int | float | None) -> float | None:
    """Convierte un monto en texto a float. Devuelve None si no es válido."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = _LIMPIEZA.sub("", str(valor)).strip()
    if not texto:
        return None
    # Formato AR: el último separador es la coma decimal.
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None
