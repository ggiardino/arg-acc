"""Tests del pipeline de Declaraciones Juradas Patrimoniales."""

from __future__ import annotations

import pytest

from aracc_etl.pipelines.declaraciones_juradas import (
    DeclaracionesJuradasPipeline,
    _clasificar_archivo,
)

from .conftest import FIXTURES

DATA_DIR = str(FIXTURES)  # contiene ddjj/raw/*.csv


def _pipeline(driver, **kw):
    return DeclaracionesJuradasPipeline(
        driver=driver, data_dir=DATA_DIR, anio=2023, offline=True, **kw
    )


# ── clasificación de archivos ───────────────────────────────
@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("declaraciones-juradas-2023-consolidado-al-20240101.csv", "declaraciones"),
        ("declaraciones-juradas-bienes-2023-consolidado.csv", "bienes"),
        ("declaraciones-juradas-deudas-2023-consolidado.csv", "deudas"),
        ("declaraciones-juradas-grupo-familiar-2023.csv", "familiares"),
        ("otra-cosa.csv", None),
    ],
)
def test_clasificar_archivo(nombre, esperado):
    assert _clasificar_archivo(nombre) == esperado


# ── transform ───────────────────────────────────────────────
def test_transform_declaraciones(fake_driver):
    pipe = _pipeline(fake_driver)
    pipe.extract()
    pipe.transform()

    # 3 filas leídas; la fila con CUIT inválido (99) se descarta.
    assert pipe.rows_in == 3
    assert len(pipe._declaraciones) == 2

    por_id = {d["ddjj_id"]: d for d in pipe._declaraciones}
    g = por_id["ddjj-1001"]
    assert g["cuil"] == "27123456780"
    assert g["nombre"] == "GOMEZ JUAN"
    # patrimonio_total se deriva de total_bienes en el grafo (ver Cypher).
    assert g["total_bienes"] == 15_000_000.50
    assert g["total_deudas"] == 2_000_000.00
    # patrimonio neto = bienes - deudas
    assert g["patrimonio_neto"] == 13_000_000.50
    # el CUIL se publica enmascarado (Ley 25.326)
    assert g["cuil_parcial"] == "27-XXXXXX78-0"
    assert g["organismo_id"] == "org-ministerio-de-economia"
    assert g["proveedor_contratista"] is False

    p = por_id["ddjj-1002"]
    assert p["proveedor_contratista"] is True
    assert p["rectificativa"] == 1
    # total_deudas_final vacío -> None, neto cae al total de bienes
    assert p["total_deudas"] is None
    assert p["patrimonio_neto"] == 8_500_000.00


def test_transform_bienes_deudas_familiares(fake_driver):
    pipe = _pipeline(fake_driver)
    pipe.extract()
    pipe.transform()

    assert len(pipe._bienes) == 3
    assert len(pipe._deudas) == 1
    # 2 familiares en el CSV; el de CUIT 0 (sin clave) se omite.
    assert len(pipe._familiares) == 1

    fam = pipe._familiares[0]
    assert fam["cuil_titular"] == "27123456780"
    assert fam["cuil_familiar"] == "27999999994"
    assert fam["vinculo"] == "Conyuge"

    bien = next(b for b in pipe._bienes if b["descripcion"] == "Inmueble en CABA")
    assert bien["valor"] == 10_000_000.00
    assert bien["periodo"] == "cierre"
    assert bien["ddjj_id"] == "ddjj-1001"


def test_ids_deterministas(fake_driver):
    """Re-transformar produce ids idénticos -> carga idempotente."""
    ids_1 = {b["bien_id"] for b in _run_transform(fake_driver)._bienes}
    ids_2 = {b["bien_id"] for b in _run_transform(fake_driver)._bienes}
    assert ids_1 == ids_2
    assert len(ids_1) == 3  # sin colisiones


def _run_transform(driver):
    pipe = _pipeline(driver)
    pipe.extract()
    pipe.transform()
    return pipe


# ── load + run completo ─────────────────────────────────────
def test_run_completo(fake_driver):
    pipe = _pipeline(fake_driver)
    pipe.run()

    assert pipe.rows_loaded == 2
    queries = " ".join(q for q, _ in fake_driver.calls)
    # se ejecutaron las cargas de las 4 entidades
    assert "MERGE (d:DeclaracionJurada" in queries
    assert "MERGE (b:BienDeclarado" in queries
    assert "MERGE (deuda:Deuda" in queries
    assert "FAMILIAR_DE" in queries
    # la corrida quedó registrada como loaded (idempotencia/auditoría)
    corridas = [
        p for q, p in fake_driver.calls if "CorridaIngesta" in q and "estado" in p
    ]
    assert corridas[-1]["estado"] == "loaded"


def test_requiere_anio(fake_driver):
    with pytest.raises(ValueError, match="anio"):
        DeclaracionesJuradasPipeline(driver=fake_driver, data_dir=DATA_DIR)


def test_offline_sin_archivos(fake_driver, tmp_path):
    """Sin archivos locales y en modo offline, extract falla con claridad."""
    pipe = DeclaracionesJuradasPipeline(
        driver=fake_driver, data_dir=str(tmp_path), anio=2099, offline=True
    )
    with pytest.raises(FileNotFoundError, match="DDJJ 2099"):
        pipe.extract()
