# ar-acc — Roadmap

De MVP a plataforma de inteligencia de grafos con IA. Cada fase tiene un
criterio de salida medible.

---

## Fase 0 — Fundación (semanas 1-4)

Adaptar la base heredada de `br-acc` al contexto argentino.

- [ ] Fork de `br-acc`; renombre `bracc` → `aracc`, `bracc_etl` → `aracc_etl`.
- [ ] Esquema Neo4j AR aplicado (`aracc/schema/init-neo4j.cypher`).
- [ ] Transforms argentinos: CUIT/CUIL (dígito verificador), montos
      (formato `1.234,56`), fechas.
- [ ] Stack Docker arriba (Neo4j + API + frontend) con grafo sintético.
- [ ] Pipelines `datos_gob_ar` y `georef` en estado `partial`.
- [ ] Documentación legal argentina (Ley 27.275 / Ley 25.326).

**Salida:** `make bootstrap-demo` levanta un grafo navegable en < 10 min.

---

## Fase 1 — MVP (meses 2-4)

Primer producto útil para periodistas y ciudadanía.

- [ ] Pipelines: COMPR.AR, Boletín Oficial, DDJJ (OA), padrón AFIP.
- [ ] Entidades núcleo: `Persona`, `Empresa`, `Funcionario`, `Organismo`,
      `Contrato`, `Licitacion`.
- [ ] Las 6 reglas de detección base (`aracc/queries/deteccion.cypher`).
- [ ] Frontend: búsqueda, explorador de grafo, fichas de entidad.
- [ ] API REST pública con identificadores enmascarados.
- [ ] CI verde: tests por pipeline con fixtures.

**Salida:** un usuario busca una empresa y ve sus contratos, socios y
señales, cada una citando su fuente oficial.

---

## Fase 2 — Versión 1.0 (meses 5-9)

Cobertura amplia y reproducibilidad.

- [ ] Pipelines: CONTRAT.AR, CNE (candidaturas + aportes), Presupuesto
      Abierto, datos de Justicia.
- [ ] Resolución de entidades probabilística (mismo apoderado /
      domicilio / nombre normalizado) con score de confianza.
- [ ] Capa **GraphQL** (`api/src/aracc/graphql`) además de REST.
- [ ] 2-3 provincias integradas (`pipelines/provincial/`).
- [ ] Reportes de investigación reproducibles (export PDF con fuentes).
- [ ] Scheduling Prefect en producción.

**Salida:** cobertura nacional + provincial; toda señal es reproducible
de extremo a extremo.

---

## Fase 3 — Avanzado con IA (meses 10+)

Inteligencia de grafos.

- [ ] **Neo4j GDS:** detección de comunidades (Louvain) sobre redes
      societarias; centralidad (PageRank, betweenness) para detectar
      intermediarios y nodos puente.
- [ ] **Scoring de riesgo con ML:** modelo supervisado entrenado sobre
      casos públicos conocidos (sanciones, condenas firmes) que pondera
      las señales — siempre como *hipótesis*, nunca como veredicto.
- [ ] **NLP sobre el Boletín Oficial:** extracción de entidades y
      relaciones desde el texto de los actos administrativos.
- [ ] **Alertas en tiempo real:** suscripción a una entidad o patrón;
      notificación ante nuevos contratos, designaciones o aportes.
- [ ] **API de embeddings de grafo** para similitud estructural entre
      redes de contratación.

**Salida:** la plataforma prioriza dónde mirar; los humanos investigan.

---

## Principios transversales

- **No acusar.** Toda salida es una hipótesis verificable contra la
  fuente citada. La presunción de inocencia es inviolable.
- **Trazabilidad.** Ningún dato sin `:SEGUN_FUENTE`.
- **Idempotencia.** Re-ejecutar cualquier pipeline es seguro.
- **Federalismo.** El diseño trata a provincias y municipios como
  ciudadanos de primera, no como un agregado posterior.
