"""Fixtures de test para ar-acc.

Provee un driver Neo4j falso que registra las consultas ejecutadas sin
necesitar una base de datos real, de modo que los pipelines pueden
testearse en CI sin Neo4j.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeSession:
    """Sesión Neo4j falsa: registra cada `run` en `calls`."""

    def __init__(self, calls: list) -> None:
        self._calls = calls

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def run(self, query: str, parameters: dict | None = None, **kwargs):
        params = {**(parameters or {}), **kwargs}
        self._calls.append((query, params))
        return []


class FakeDriver:
    """Driver Neo4j falso. `calls` acumula todas las consultas ejecutadas."""

    def __init__(self) -> None:
        self.calls: list = []

    def session(self, *args, **kwargs) -> FakeSession:
        return FakeSession(self.calls)

    def close(self) -> None:
        return None


@pytest.fixture
def fake_driver() -> FakeDriver:
    return FakeDriver()
