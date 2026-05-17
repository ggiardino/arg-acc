"""Utilidades de descarga de datos crudos desde fuentes oficiales.

Resuelve recursos de portales CKAN (datos.gob.ar, datos.jus.gob.ar) y
los descarga de forma resiliente, con reintentos y backoff exponencial.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MAX_REINTENTOS = 4
_TIMEOUT = 60.0


def descargar(url: str, destino: Path, *, forzar: bool = False) -> Path:
    """Descarga `url` a `destino`. Si el archivo ya existe, no re-descarga.

    Reintenta hasta 4 veces con backoff exponencial (2s, 4s, 8s, 16s).
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not forzar:
        logger.info("ya presente, se omite descarga: %s", destino.name)
        return destino

    ultimo_error: Exception | None = None
    for intento in range(_MAX_REINTENTOS):
        try:
            with httpx.stream("GET", url, timeout=_TIMEOUT, follow_redirects=True) as resp:
                resp.raise_for_status()
                tmp = destino.with_suffix(destino.suffix + ".part")
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        fh.write(chunk)
                tmp.replace(destino)  # escritura atómica
            logger.info("descargado: %s", destino.name)
            return destino
        except (httpx.HTTPError, OSError) as exc:
            ultimo_error = exc
            espera = 2 ** (intento + 1)
            logger.warning("descarga falló (%s), reintento en %ss", exc, espera)
            time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo_error}")


def listar_recursos_ckan(portal: str, dataset_id: str) -> list[dict]:
    """Devuelve los recursos (archivos) de un dataset CKAN.

    `portal` es la base del portal, ej. 'https://datos.jus.gob.ar'.
    Cada recurso es un dict con al menos `name`, `url` y `format`.
    """
    url = f"{portal.rstrip('/')}/api/3/action/package_show"
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, params={"id": dataset_id})
        resp.raise_for_status()
        payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN package_show falló para {dataset_id}")
    return payload["result"].get("resources", [])
