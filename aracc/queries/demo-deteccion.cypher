// ============================================================
//  ar-acc — Queries de detección LISTAS PARA EJECUTAR
//
//  Versión del set de detección con los parámetros ya rellenados
//  para correr contra el grafo de demo sintético (seed-demo.cypher).
//  Copiá y pegá cada bloque en el Neo4j Browser (http://localhost:7474).
//
//  La versión parametrizada y completa está en deteccion.cypher.
//  Recordatorio: las señales son hipótesis a verificar, no acusaciones.
// ============================================================


// ── 1. Enriquecimiento patrimonial (umbral +50%) ────────────
// Esperado: GOMEZ JUAN CARLOS, patrimonio 10M -> 28M.
MATCH (p:Persona)-[:PRESENTO]->(d1:DeclaracionJurada),
      (p)-[:PRESENTO]->(d2:DeclaracionJurada)
WHERE d2.anio = d1.anio + 1
  AND d1.patrimonio_total > 0
  AND (d2.patrimonio_total - d1.patrimonio_total) / d1.patrimonio_total >= 0.5
OPTIONAL MATCH (p)-[:SOCIO_DE]->(:Empresa)-[:ADJUDICATARIA_DE]->(ct:Contrato)
WHERE ct.fecha >= d1.fecha AND ct.fecha <= d2.fecha
RETURN p.nombre AS funcionario, d1.anio AS desde, d2.anio AS hasta,
       d2.patrimonio_total - d1.patrimonio_total AS delta_patrimonio,
       sum(ct.monto) AS contratos_en_el_periodo;


// ── 2. Adjudicaciones directas repetidas (>= 3) ─────────────
// Esperado: Ministerio de Infraestructura -> Constructora del Sur, 3.
MATCH (o:Organismo)-[:CONTRATA]->(c:Contrato)<-[:ADJUDICATARIA_DE]-(e:Empresa)
WHERE c.modalidad = 'CONTRATACION_DIRECTA'
WITH o, e, count(c) AS n_directas, sum(c.monto) AS monto_total
WHERE n_directas >= 3
RETURN o.nombre AS organismo, e.razon_social AS proveedor,
       n_directas, monto_total
ORDER BY monto_total DESC;


// ── 3. Conflicto de interés (solapamiento temporal) ─────────
// Esperado: GOMEZ es socio de Constructora del Sur, que contrata
// con el organismo donde él es funcionario.
MATCH (p:Persona)-[:ES_FUNCIONARIO]->(:Funcionario)-[oc:OCUPA]->(:Cargo)-[:EN]->(o:Organismo)
MATCH (p)-[soc:SOCIO_DE]->(e:Empresa)-[:ADJUDICATARIA_DE]->(c:Contrato)<-[:CONTRATA]-(o)
WHERE c.fecha >= oc.desde AND (oc.hasta IS NULL OR c.fecha <= oc.hasta)
  AND c.fecha >= soc.desde AND (soc.hasta IS NULL OR c.fecha <= soc.hasta)
RETURN p.nombre AS funcionario, o.nombre AS organismo,
       e.razon_social AS empresa, soc.pct AS participacion_pct,
       c.contrato_id, c.monto
ORDER BY c.monto DESC;


// ── 4. Empresas con el mismo apoderado ──────────────────────
// Esperado: PEREZ MARIA es apoderada de dos empresas.
MATCH (p:Persona)-[:APODERADO_DE]->(e:Empresa)
WITH p, collect(DISTINCT e.razon_social) AS empresas
WHERE size(empresas) >= 2
RETURN p.nombre AS apoderado, empresas;


// ── 5. Empresas que comparten domicilio ─────────────────────
// Esperado: Constructora del Sur y Vialidad Norte, misma dirección.
MATCH (e1:Empresa)-[:TIENE_DOMICILIO]->(d:Domicilio)<-[:TIENE_DOMICILIO]-(e2:Empresa)
WHERE e1.cuit < e2.cuit
RETURN d.direccion_normalizada AS domicilio,
       e1.razon_social AS empresa_a, e2.razon_social AS empresa_b;


// ── 6. Proveedor del Estado que aporta a una campaña ────────
// Esperado: Constructora del Sur aporta a un partido y además
// tiene contratos con el Estado en el mismo período.
MATCH (e:Empresa)-[a:APORTO]->(pt:Partido)
MATCH (e)-[:ADJUDICATARIA_DE]->(c:Contrato)
WHERE abs(toInteger(left(c.fecha, 4)) - a.anio) <= 1
RETURN e.razon_social AS proveedor, pt.nombre AS partido,
       a.anio AS anio_aporte, a.monto AS monto_aporte,
       count(DISTINCT c) AS contratos_cercanos, sum(c.monto) AS monto_contratos;


// ── Resumen del grafo ───────────────────────────────────────
// Cuántos nodos hay de cada tipo.
MATCH (n)
RETURN labels(n)[0] AS tipo, count(*) AS cantidad
ORDER BY cantidad DESC;
