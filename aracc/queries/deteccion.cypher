// ============================================================
//  ar-acc — Queries Cypher de detección de señales de riesgo
//
//  IMPORTANTE: cada query devuelve HIPÓTESIS a verificar contra la
//  fuente oficial citada (:FuenteDocumento). No constituyen prueba ni
//  imputación. Rige la presunción de inocencia.
//
//  Parámetros (entre $) se inyectan desde la capa de servicios.
// ============================================================


// ── 1. Enriquecimiento patrimonial ──────────────────────────
// Salto del patrimonio declarado entre dos DDJJ consecutivas de un
// funcionario, correlacionado con contratos públicos ganados en ese
// período por empresas en las que la persona tiene participación.
MATCH (p:Persona)-[:PRESENTO]->(d1:DeclaracionJurada),
      (p)-[:PRESENTO]->(d2:DeclaracionJurada)
WHERE d2.anio = d1.anio + 1
  AND d1.patrimonio_total > 0
  AND (d2.patrimonio_total - d1.patrimonio_total)
        / d1.patrimonio_total >= $umbral_crecimiento   // ej. 0.5 = +50%
OPTIONAL MATCH (p)-[s:SOCIO_DE]->(emp:Empresa)-[adj:ADJUDICATARIA_DE]->(ct:Contrato)
WHERE date(ct.fecha) >= date(d1.fecha)
  AND date(ct.fecha) <= date(d2.fecha)
WITH p, d1, d2,
     d2.patrimonio_total - d1.patrimonio_total       AS delta_patrimonio,
     sum(ct.monto)                                   AS contratos_periodo,
     count(DISTINCT ct)                              AS n_contratos
RETURN p.nombre                                      AS funcionario,
       d1.anio AS anio_desde, d2.anio AS anio_hasta,
       delta_patrimonio, contratos_periodo, n_contratos
ORDER BY delta_patrimonio DESC;


// ── 2a. Adjudicaciones directas repetidas ───────────────────
// Mismo organismo contrata reiteradamente al mismo proveedor por
// contratación directa, eludiendo el proceso licitatorio competitivo.
MATCH (o:Organismo)-[:CONTRATA]->(c:Contrato)<-[:ADJUDICATARIA_DE]-(e:Empresa)
WHERE c.modalidad IN ['CONTRATACION_DIRECTA', 'ADJUDICACION_SIMPLE']
  AND date(c.fecha) >= date($desde)
WITH o, e, count(c) AS n_directas, sum(c.monto) AS monto_total,
     collect(c.contrato_id)[..20] AS contratos
WHERE n_directas >= $umbral_directas                  // ej. 5
RETURN o.nombre AS organismo, e.razon_social AS proveedor, e.cuit,
       n_directas, monto_total, contratos
ORDER BY monto_total DESC;


// ── 2b. Fraccionamiento para evadir el tope licitatorio ─────
// Múltiples contratos del mismo organismo al mismo proveedor, en una
// ventana corta, cada uno justo por debajo del umbral que obligaría a
// llamar a licitación pública.
MATCH (o:Organismo)-[:CONTRATA]->(c:Contrato)<-[:ADJUDICATARIA_DE]-(e:Empresa)
WHERE c.monto <= $tope_modulos
  AND c.monto >= $tope_modulos * 0.8
WITH o, e, c
ORDER BY c.fecha
WITH o, e, collect(c) AS cs
WHERE size(cs) >= $min_fraccionado                    // ej. 3
  AND duration.inDays(date(cs[0].fecha),
                      date(cs[-1].fecha)).days <= $ventana_dias
RETURN o.nombre AS organismo, e.razon_social AS proveedor,
       size(cs) AS n_contratos,
       reduce(s = 0.0, x IN cs | s + x.monto) AS monto_acumulado,
       [x IN cs | x.fecha] AS fechas;


// ── 2c. Sobreprecio por ítem vs. mediana de mercado ─────────
// Ítems contratados por encima del percentil de precio observado para
// el mismo objeto en el resto del grafo (señal de sobreprecio).
MATCH (c:Contrato)
WHERE c.objeto = $objeto AND c.precio_unitario IS NOT NULL
WITH percentileCont(c.precio_unitario, 0.5) AS mediana,
     percentileCont(c.precio_unitario, 0.9) AS p90
MATCH (e:Empresa)-[:ADJUDICATARIA_DE]->(c2:Contrato)
WHERE c2.objeto = $objeto AND c2.precio_unitario > p90
RETURN e.razon_social AS proveedor, c2.contrato_id,
       c2.precio_unitario, mediana,
       round(100.0 * (c2.precio_unitario - mediana) / mediana) AS sobreprecio_pct
ORDER BY sobreprecio_pct DESC;


// ── 3a. Empresas que comparten apoderado o representante legal ──
MATCH (p:Persona)-[r:APODERADO_DE|REPRESENTA_LEGAL]->(e:Empresa)
WITH p, collect(DISTINCT e) AS empresas
WHERE size(empresas) >= 2
RETURN p.nombre AS persona, p.cuil_parcial,
       [e IN empresas | {cuit: e.cuit, razon_social: e.razon_social}] AS empresas
ORDER BY size(empresas) DESC;


// ── 3b. Empresas con el mismo domicilio compitiendo en una licitación ──
// Indicador clásico de oferentes "de cartón" / colusión.
MATCH (l:Licitacion)<-[:DERIVA_DE]-(:Contrato)<-[:ADJUDICATARIA_DE]-(e1:Empresa)
MATCH (e1)-[:TIENE_DOMICILIO]->(d:Domicilio)<-[:TIENE_DOMICILIO]-(e2:Empresa)
WHERE e1.cuit < e2.cuit
  AND (e2)-[:ADJUDICATARIA_DE]->(:Contrato)-[:DERIVA_DE]->(l)
RETURN l.licitacion_id AS licitacion,
       d.direccion_normalizada AS domicilio_compartido,
       e1.razon_social AS empresa_a, e2.razon_social AS empresa_b;


// ── 4. Conflicto de interés (con solapamiento temporal) ─────
// Funcionario que es socio de una empresa que contrata con su propio
// organismo, mientras ocupa el cargo (vigencias que se solapan).
MATCH (p:Persona)-[:ES_FUNCIONARIO]->(f:Funcionario)-[oc:OCUPA]->(:Cargo)-[:EN]->(o:Organismo)
MATCH (p)-[soc:SOCIO_DE]->(e:Empresa)-[adj:ADJUDICATARIA_DE]->(c:Contrato)<-[:CONTRATA]-(o)
WHERE date(c.fecha) >= date(oc.desde)
  AND (oc.hasta IS NULL OR date(c.fecha) <= date(oc.hasta))
  AND date(c.fecha) >= date(soc.desde)
  AND (soc.hasta IS NULL OR date(c.fecha) <= date(soc.hasta))
RETURN p.nombre AS funcionario, o.nombre AS organismo,
       e.razon_social AS empresa, soc.pct AS participacion_pct,
       c.contrato_id, c.monto, c.fecha
ORDER BY c.monto DESC;


// ── 5. Puerta giratoria (revolving door) ────────────────────
// Persona que dejó un cargo público y dentro de una ventana de tiempo
// pasó a una empresa que contrata con el mismo organismo donde sirvió.
MATCH (p:Persona)-[:ES_FUNCIONARIO]->(:Funcionario)-[oc:OCUPA]->(:Cargo)-[:EN]->(o:Organismo)
WHERE oc.hasta IS NOT NULL
MATCH (p)-[soc:SOCIO_DE|APODERADO_DE]->(e:Empresa)-[:ADJUDICATARIA_DE]->(c:Contrato)<-[:CONTRATA]-(o)
WHERE date(soc.desde) >= date(oc.hasta)
  AND duration.inMonths(date(oc.hasta), date(soc.desde)).months <= $ventana_meses
RETURN p.nombre AS persona, o.nombre AS organismo,
       oc.hasta AS fin_cargo, soc.desde AS ingreso_empresa,
       e.razon_social AS empresa, sum(c.monto) AS contratos_post_cargo
ORDER BY contratos_post_cargo DESC;


// ── 6a. Aportante de campaña que supera el tope legal ───────
MATCH (aportante)-[a:APORTO]->(pt:Partido)
WHERE a.anio = $anio_electoral
WITH aportante, pt, sum(a.monto) AS total_aportado
WHERE total_aportado > $tope_aporte
RETURN labels(aportante)[0] AS tipo,
       coalesce(aportante.nombre, aportante.razon_social) AS aportante,
       pt.nombre AS partido, total_aportado, $tope_aporte AS tope;


// ── 6b. Proveedor del Estado que aporta a una campaña ───────
// Las empresas contratistas del Estado tienen restricciones para
// aportar; cruce de aportes con adjudicaciones del mismo período.
MATCH (e:Empresa)-[a:APORTO]->(pt:Partido)
MATCH (e)-[:ADJUDICATARIA_DE]->(c:Contrato)
WHERE abs(c.fecha.year - a.anio) <= 1
RETURN e.razon_social AS proveedor, e.cuit,
       pt.nombre AS partido, a.anio AS anio_aporte, a.monto AS monto_aporte,
       count(DISTINCT c) AS contratos_cercanos,
       sum(c.monto) AS monto_contratos
ORDER BY monto_aporte DESC;


// ── 6c. Aporte incompatible con el patrimonio declarado ─────
// Persona que aportó más de lo que su DDJJ patrimonial del año
// sugiere como capacidad razonable.
MATCH (p:Persona)-[a:APORTO]->(pt:Partido)
MATCH (p)-[:PRESENTO]->(d:DeclaracionJurada)
WHERE d.anio = a.anio
  AND a.monto > d.patrimonio_total * $ratio_incompatible   // ej. 0.3
RETURN p.nombre AS aportante, pt.nombre AS partido,
       a.anio, a.monto AS aporte, d.patrimonio_total AS patrimonio_declarado;


// ── Apoyo: trazabilidad de cualquier señal a su fuente ──────
// Dado un nodo, devuelve los documentos oficiales que lo respaldan.
MATCH (n)-[:SEGUN_FUENTE]->(doc:FuenteDocumento)
WHERE elementId(n) = $element_id
RETURN doc.source_id, doc.url, doc.hash, doc.fecha_captura, doc.fecha_publicacion;
