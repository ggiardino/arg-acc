"""Normalización y validación de identificadores tributarios argentinos.

CUIT/CUIL: 11 dígitos con dígito verificador (módulo 11). Formato
canónico para el grafo: solo dígitos, sin guiones.

En modo público se publica un identificador *parcial* (enmascarado)
para cumplir el principio de minimización de la Ley 25.326.
"""

from __future__ import annotations

import re

_SOLO_DIGITOS = re.compile(r"\D+")
# Pesos del cálculo del dígito verificador de CUIT/CUIL.
_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar_cuit(valor: str | int | None) -> str | None:
    """Devuelve el CUIT/CUIL como 11 dígitos, o None si es inválido."""
    if valor is None:
        return None
    digitos = _SOLO_DIGITOS.sub("", str(valor))
    if len(digitos) != 11:
        return None
    return digitos if cuit_valido(digitos) else None


def cuit_valido(digitos: str) -> bool:
    """Valida el dígito verificador (módulo 11)."""
    if len(digitos) != 11 or not digitos.isdigit():
        return False
    suma = sum(int(d) * p for d, p in zip(digitos[:10], _PESOS, strict=True))
    resto = 11 - (suma % 11)
    verificador = 0 if resto == 11 else (9 if resto == 10 else resto)
    return verificador == int(digitos[10])


def cuit_formateado(digitos: str) -> str:
    """20-12345678-9 a partir de 11 dígitos."""
    return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10:]}"


def cuit_enmascarado(digitos: str | None) -> str | None:
    """Identificador parcial para el modo público.

    Conserva prefijo (tipo de persona) y dígito verificador; oculta el
    núcleo coincidente con el DNI. Ej.: '20-XXXXXX78-9'.
    """
    if not digitos or len(digitos) != 11:
        return None
    return f"{digitos[:2]}-XXXXXX{digitos[8:10]}-{digitos[10]}"


def dni_desde_cuit(digitos: str | None) -> str | None:
    """Extrae el DNI embebido en un CUIT/CUIL de persona física (20/23/24/27)."""
    if not digitos or len(digitos) != 11:
        return None
    if digitos[:2] not in {"20", "23", "24", "27"}:
        return None
    return digitos[2:10].lstrip("0") or None
