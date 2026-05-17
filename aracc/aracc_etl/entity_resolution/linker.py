"""Resolutor de entidades: arma bloques, compara y propone candidatos.

Toma una colección de registros (cada uno con `id` y `nombre`, y de
forma opcional `cuit` y `domicilio_id`) y devuelve pares que
probablemente son la misma entidad del mundo real.

Los candidatos no se fusionan automáticamente: se materializan como
relaciones `POSIBLE_MISMO_QUE` en el grafo, para revisión humana. La
fusión destructiva nunca es automática — un falso positivo uniría a dos
personas distintas, y eso es inaceptable en un proyecto de transparencia.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from aracc_etl.entity_resolution.matcher import (
    clave_bloqueo,
    nivel_confianza,
    similitud,
)


@dataclass(frozen=True)
class CandidatoMatch:
    """Un par de registros que probablemente son la misma entidad."""

    id_a: str
    id_b: str
    score: float
    confianza: str
    motivo: str


class EntityResolver:
    """Resuelve duplicados dentro de un conjunto de registros.

    `empresa=True` aplica la normalización de razones sociales (elimina
    sufijos societarios) en lugar de la de nombres de personas.
    """

    def __init__(self, *, empresa: bool = False, umbral: float = 0.65) -> None:
        self.empresa = empresa
        self.umbral = umbral

    def resolver(self, registros: list[dict]) -> list[CandidatoMatch]:
        """Devuelve los candidatos de match por encima del umbral.

        Cada registro es un dict con: `id` (str, requerido), `nombre`
        (str, requerido), `cuit` (opcional), `domicilio_id` (opcional).

        Cada registro entra en dos clases de bloque: uno por nombre y,
        si tiene CUIT, uno por CUIT — así una identidad con el mismo
        CUIT se detecta aunque los nombres caigan en bloques distintos.
        """
        bloques: dict[tuple, list[dict]] = defaultdict(list)
        for reg in registros:
            clave = clave_bloqueo(reg.get("nombre", ""), empresa=self.empresa)
            bloques[("nombre", clave)].append(reg)
            if reg.get("cuit"):
                bloques[("cuit", reg["cuit"])].append(reg)

        # Un par puede surgir en varios bloques: se conserva el mejor.
        mejor: dict[tuple[str, str], CandidatoMatch] = {}
        for grupo in bloques.values():
            for cand in self._comparar_grupo(grupo):
                clave_par = (cand.id_a, cand.id_b)
                actual = mejor.get(clave_par)
                if actual is None or cand.score > actual.score:
                    mejor[clave_par] = cand
        # Más confiables primero.
        return sorted(mejor.values(), key=lambda c: c.score, reverse=True)

    def _comparar_grupo(self, grupo: list[dict]) -> list[CandidatoMatch]:
        salida: list[CandidatoMatch] = []
        for i in range(len(grupo)):
            for j in range(i + 1, len(grupo)):
                cand = self._comparar(grupo[i], grupo[j])
                if cand is not None:
                    salida.append(cand)
        return salida

    def _comparar(self, a: dict, b: dict) -> CandidatoMatch | None:
        cuit_a, cuit_b = a.get("cuit"), b.get("cuit")
        cuit_compartido = bool(cuit_a) and cuit_a == cuit_b

        score = similitud(
            a.get("nombre", ""), b.get("nombre", ""), empresa=self.empresa
        )
        # Un CUIT compartido es identidad: el score no debe bajar la nota.
        if cuit_compartido:
            score = max(score, 1.0)
        elif score < self.umbral:
            return None

        dom_a, dom_b = a.get("domicilio_id"), b.get("domicilio_id")
        domicilio_compartido = bool(dom_a) and dom_a == dom_b

        confianza = nivel_confianza(
            score,
            cuit_compartido=cuit_compartido,
            domicilio_compartido=domicilio_compartido,
        )
        if confianza == "descartado":
            return None

        motivos = []
        if cuit_compartido:
            motivos.append("CUIT/CUIL idéntico")
        if domicilio_compartido:
            motivos.append("domicilio compartido")
        motivos.append(f"similitud de nombre {score:.2f}")

        id_a, id_b = sorted((str(a["id"]), str(b["id"])))
        return CandidatoMatch(
            id_a=id_a,
            id_b=id_b,
            score=score,
            confianza=confianza,
            motivo="; ".join(motivos),
        )


# Etiqueta del nodo según el tipo de entidad resuelta.
def cypher_posible_mismo_que(label: str = "Persona") -> str:
    """Cypher parametrizado que materializa los candidatos en el grafo.

    Espera el parámetro $rows: lista de dicts con las claves de
    `CandidatoMatch`. Crea relaciones `POSIBLE_MISMO_QUE` no destructivas
    para revisión; nunca fusiona nodos.
    """
    return f"""
    UNWIND $rows AS row
    MATCH (a:{label}) WHERE elementId(a) = row.id_a OR a.cuil = row.id_a
                         OR a.cuit = row.id_a
    MATCH (b:{label}) WHERE elementId(b) = row.id_b OR b.cuil = row.id_b
                         OR b.cuit = row.id_b
    MERGE (a)-[r:POSIBLE_MISMO_QUE]-(b)
      SET r.score = row.score,
          r.confianza = row.confianza,
          r.motivo = row.motivo,
          r.revisado = false
    """
