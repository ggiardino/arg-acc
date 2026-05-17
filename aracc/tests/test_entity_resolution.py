"""Tests del módulo básico de resolución de entidades."""

from __future__ import annotations

from aracc_etl.entity_resolution import (
    EntityResolver,
    clave_bloqueo,
    cypher_posible_mismo_que,
    nivel_confianza,
    normalizar_nombre,
    normalizar_razon_social,
    similitud,
)


# ── normalización ───────────────────────────────────────────
def test_normalizar_nombre_orden_y_acentos():
    # 'Apellido, Nombre' y 'Nombre Apellido' convergen.
    assert normalizar_nombre("GOMEZ, Juan Carlos") == normalizar_nombre(
        "Juan Carlos Gómez"
    )


def test_normalizar_nombre_ignora_particulas():
    assert normalizar_nombre("María de la Paz Díaz") == normalizar_nombre(
        "Maria Paz Diaz"
    )


def test_normalizar_razon_social_quita_sufijos():
    # Variantes societarias de la misma empresa convergen.
    assert normalizar_razon_social("Constructora del Sur S.A.") == (
        normalizar_razon_social("CONSTRUCTORA DEL SUR S.R.L.")
    )
    assert "SA" not in normalizar_razon_social("Vialidad SA").split()


# ── similitud ───────────────────────────────────────────────
def test_similitud_identica():
    assert similitud("Juan Pérez", "PEREZ, JUAN") == 1.0


def test_similitud_parecida_vs_distinta():
    parecida = similitud("Juan Carlos Gómez", "Juan C. Gomez")
    distinta = similitud("Juan Carlos Gómez", "Marta Fernández")
    assert parecida > 0.6
    assert distinta < 0.3


def test_similitud_empresa_ignora_sufijo():
    assert similitud(
        "Constructora del Sur SA", "Constructora del Sur SRL", empresa=True
    ) == 1.0


# ── bloqueo y confianza ─────────────────────────────────────
def test_clave_bloqueo_agrupa():
    assert clave_bloqueo("GOMEZ, Juan") == clave_bloqueo("Juan Gómez")


def test_nivel_confianza():
    assert nivel_confianza(0.5, cuit_compartido=True) == "alta"
    assert nivel_confianza(0.95) == "alta"
    assert nivel_confianza(0.82, domicilio_compartido=True) == "alta"
    assert nivel_confianza(0.82) == "media"
    assert nivel_confianza(0.70) == "baja"
    assert nivel_confianza(0.40) == "descartado"


# ── resolver ────────────────────────────────────────────────
def test_resolver_personas_detecta_duplicado():
    registros = [
        {"id": "p1", "nombre": "GOMEZ, Juan Carlos"},
        {"id": "p2", "nombre": "Juan Carlos Gómez"},
        {"id": "p3", "nombre": "Marta Fernández"},
    ]
    candidatos = EntityResolver().resolver(registros)
    assert len(candidatos) == 1
    c = candidatos[0]
    assert {c.id_a, c.id_b} == {"p1", "p2"}
    assert c.confianza == "alta"


def test_resolver_cuit_compartido_es_alta_confianza():
    registros = [
        # Nombres distintos pero mismo CUIL -> identidad.
        {"id": "p1", "nombre": "Juan Gómez", "cuit": "20111111112"},
        {"id": "p2", "nombre": "J C Gomez", "cuit": "20111111112"},
    ]
    candidatos = EntityResolver().resolver(registros)
    assert len(candidatos) == 1
    assert candidatos[0].confianza == "alta"
    assert candidatos[0].score == 1.0
    assert "CUIT/CUIL idéntico" in candidatos[0].motivo


def test_resolver_empresas_con_domicilio():
    registros = [
        {"id": "e1", "nombre": "Constructora del Sur S.A.", "domicilio_id": "d9"},
        {"id": "e2", "nombre": "CONSTRUCTORA DEL SUR SRL", "domicilio_id": "d9"},
        {"id": "e3", "nombre": "Panadería La Esquina"},
    ]
    candidatos = EntityResolver(empresa=True).resolver(registros)
    assert len(candidatos) == 1
    assert {candidatos[0].id_a, candidatos[0].id_b} == {"e1", "e2"}
    assert "domicilio compartido" in candidatos[0].motivo


def test_resolver_ignora_pares_debiles():
    registros = [
        {"id": "p1", "nombre": "Juan Pérez"},
        {"id": "p2", "nombre": "Juana Paredes"},
    ]
    # Comparten bloque pero la similitud no alcanza el umbral.
    assert EntityResolver().resolver(registros) == []


def test_cypher_posible_mismo_que_parametrizable():
    cypher = cypher_posible_mismo_que("Empresa")
    assert "MATCH (a:Empresa)" in cypher
    assert "POSIBLE_MISMO_QUE" in cypher
    assert "r.revisado = false" in cypher  # no destructivo: requiere revisión
