"""Router FastAPI del dashboard estilo terminal de ar-acc.

Se monta sobre la aplicación principal (`api/index.py`) y expone:

  GET /dashboard               -> interfaz web estilo terminal
  GET /api/dashboard/ls        -> navegación jerárquica (JSON)
  GET /api/dashboard/search    -> búsqueda de funcionarios (JSON)
"""

from __future__ import annotations

import pathlib

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

from dashboard.service import DashboardService

router = APIRouter()
_service = DashboardService()
_HTML = (pathlib.Path(__file__).resolve().parent / "terminal.html").read_text(
    encoding="utf-8"
)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_home() -> HTMLResponse:
    """Sirve la interfaz web del dashboard de inconsistencias."""
    return HTMLResponse(_HTML)


@router.get("/api/dashboard/ls")
def dashboard_ls(
    path: str = Query("/", description="Ruta jerárquica a listar"),
    q: str | None = Query(None, description="Texto de búsqueda opcional"),
) -> JSONResponse:
    """Devuelve la vista correspondiente a una ruta del árbol."""
    return JSONResponse(_service.navegar(path, q))


@router.get("/api/dashboard/search")
def dashboard_search(
    q: str = Query(..., min_length=1, description="Nombre o CUIL a buscar"),
) -> JSONResponse:
    """Busca funcionarios por nombre o identificador."""
    return JSONResponse(_service.buscar(q))
