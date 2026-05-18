// ============================================================
//  ar-acc — Grafo DEMO para el dashboard de inconsistencias
//
//  DATOS 100% SINTÉTICOS. Ninguna persona, organismo ni cifra de
//  este archivo es real; cualquier coincidencia es casual. Sirve
//  para previsualizar el dashboard sin esperar la ingesta de datos
//  reales (pipelines/import_ddjj_real.py).
//
//  Reproduce los 5 detectores: salto patrimonial, descuadre interno,
//  funcionario-proveedor, años faltantes y declaración rectificada.
//
//  Aplicar:
//    cypher-shell -u neo4j -p <pass> -f dashboard/seed_demo.cypher
//
//  Idempotente (MERGE): se puede re-aplicar. No borra datos reales.
// ============================================================

// ── Fuente documental (trazabilidad) ───────────────────────
MERGE (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
  SET f.source_id = 'demo',
      f.url = 'https://datos.jus.gob.ar/dataset/declaraciones-juradas-patrimoniales-integrales',
      f.fecha_captura = '2024-01-01';

// ── Organismos (DEMO) ───────────────────────────────────────
MERGE (o:Organismo {organismo_id: 'org-demo-diputados'})
  SET o.nombre = 'Honorable Cámara de Diputados (DEMO)', o.nivel = 'nacional';
MERGE (o:Organismo {organismo_id: 'org-demo-obras'})
  SET o.nombre = 'Ministerio de Obras Públicas (DEMO)', o.nivel = 'nacional';
MERGE (o:Organismo {organismo_id: 'org-demo-municipio'})
  SET o.nombre = 'Municipalidad de Ciudad Demo (DEMO)', o.nivel = 'municipal';

// ════════════════════════════════════════════════════════════
//  CASO 1 — Salto patrimonial: dos DDJJ con +242% interanual
// ════════════════════════════════════════════════════════════
MERGE (p:Persona {cuil: 'demo-0001'})
  SET p.nombre = 'LEGISLADOR/A FICTICIO/A UNO',
      p.cuil_parcial = 'DEMO-0001', p.provincia = 'Buenos Aires';

MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0001-2021'})
  SET d.anio = 2021, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Diputado/a Nacional', d.sector = 'Publico',
      d.desde = '2019-12', d.proveedor_contratista = false,
      d.total_bienes = 12000000.0, d.total_deudas = 2000000.0,
      d.patrimonio_total = 12000000.0, d.patrimonio_neto = 10000000.0;
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0001-2022'})
  SET d.anio = 2022, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Diputado/a Nacional', d.sector = 'Publico',
      d.desde = '2019-12', d.proveedor_contratista = false,
      d.total_bienes = 41000000.0, d.total_deudas = 1000000.0,
      d.patrimonio_total = 41000000.0, d.patrimonio_neto = 40000000.0;

MATCH (p:Persona {cuil: 'demo-0001'}),
      (d1:DeclaracionJurada {ddjj_id: 'demo-0001-2021'}),
      (d2:DeclaracionJurada {ddjj_id: 'demo-0001-2022'}),
      (o:Organismo {organismo_id: 'org-demo-diputados'}),
      (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
MERGE (p)-[:PRESENTO]->(d1)
MERGE (p)-[:PRESENTO]->(d2)
MERGE (d1)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d2)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d1)-[:SEGUN_FUENTE]->(f)
MERGE (d2)-[:SEGUN_FUENTE]->(f);

MERGE (b:BienDeclarado {bien_id: 'demo-0001-2022-b1'})
  SET b.tipo = 'Inmueble', b.descripcion = 'Departamento en CABA',
      b.valor = 33000000.0, b.periodo = 'cierre', b.titularidad = '100%';
MERGE (b:BienDeclarado {bien_id: 'demo-0001-2022-b2'})
  SET b.tipo = 'Automotor', b.descripcion = 'Vehículo 0km',
      b.valor = 8000000.0, b.periodo = 'cierre', b.titularidad = '100%';
MATCH (d:DeclaracionJurada {ddjj_id: 'demo-0001-2022'}),
      (b1:BienDeclarado {bien_id: 'demo-0001-2022-b1'}),
      (b2:BienDeclarado {bien_id: 'demo-0001-2022-b2'})
MERGE (d)-[:DECLARA]->(b1)
MERGE (d)-[:DECLARA]->(b2);

// ════════════════════════════════════════════════════════════
//  CASO 2 — Años faltantes: presentó 2021 y 2023, no 2022
// ════════════════════════════════════════════════════════════
MERGE (p:Persona {cuil: 'demo-0002'})
  SET p.nombre = 'LEGISLADOR/A FICTICIO/A DOS',
      p.cuil_parcial = 'DEMO-0002', p.provincia = 'Córdoba';
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0002-2021'})
  SET d.anio = 2021, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Diputado/a Nacional', d.sector = 'Publico',
      d.proveedor_contratista = false,
      d.total_bienes = 18000000.0, d.total_deudas = 0.0,
      d.patrimonio_total = 18000000.0, d.patrimonio_neto = 18000000.0;
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0002-2023'})
  SET d.anio = 2023, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Diputado/a Nacional', d.sector = 'Publico',
      d.proveedor_contratista = false,
      d.total_bienes = 21000000.0, d.total_deudas = 0.0,
      d.patrimonio_total = 21000000.0, d.patrimonio_neto = 21000000.0;
MATCH (p:Persona {cuil: 'demo-0002'}),
      (d1:DeclaracionJurada {ddjj_id: 'demo-0002-2021'}),
      (d2:DeclaracionJurada {ddjj_id: 'demo-0002-2023'}),
      (o:Organismo {organismo_id: 'org-demo-diputados'}),
      (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
MERGE (p)-[:PRESENTO]->(d1)
MERGE (p)-[:PRESENTO]->(d2)
MERGE (d1)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d2)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d1)-[:SEGUN_FUENTE]->(f)
MERGE (d2)-[:SEGUN_FUENTE]->(f);

// ════════════════════════════════════════════════════════════
//  CASO 3 — Funcionario declarado como proveedor del Estado
// ════════════════════════════════════════════════════════════
MERGE (p:Persona {cuil: 'demo-0003'})
  SET p.nombre = 'FUNCIONARIO/A FICTICIO/A TRES',
      p.cuil_parcial = 'DEMO-0003', p.provincia = 'Santa Fe';
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0003-2022'})
  SET d.anio = 2022, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Director/a Nacional de Compras', d.sector = 'Publico',
      d.desde = '2020-03', d.proveedor_contratista = true,
      d.total_bienes = 25000000.0, d.total_deudas = 5000000.0,
      d.patrimonio_total = 25000000.0, d.patrimonio_neto = 20000000.0;
MATCH (p:Persona {cuil: 'demo-0003'}),
      (d:DeclaracionJurada {ddjj_id: 'demo-0003-2022'}),
      (o:Organismo {organismo_id: 'org-demo-obras'}),
      (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
MERGE (p)-[:PRESENTO]->(d)
MERGE (d)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d)-[:SEGUN_FUENTE]->(f);

// ════════════════════════════════════════════════════════════
//  CASO 4 — Descuadre: total de bienes != suma de bienes
// ════════════════════════════════════════════════════════════
MERGE (p:Persona {cuil: 'demo-0004'})
  SET p.nombre = 'FUNCIONARIO/A FICTICIO/A CUATRO',
      p.cuil_parcial = 'DEMO-0004', p.provincia = 'Mendoza';
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0004-2022'})
  SET d.anio = 2022, d.tipo = 'Anual', d.rectificativa = 0,
      d.cargo = 'Subsecretario/a', d.sector = 'Publico',
      d.desde = '2021-01', d.proveedor_contratista = false,
      d.total_bienes = 30000000.0, d.total_deudas = 0.0,
      d.patrimonio_total = 30000000.0, d.patrimonio_neto = 30000000.0;
MERGE (b:BienDeclarado {bien_id: 'demo-0004-2022-b1'})
  SET b.tipo = 'Inmueble', b.descripcion = 'Casa habitación',
      b.valor = 8000000.0, b.periodo = 'cierre', b.titularidad = '50%';
MATCH (p:Persona {cuil: 'demo-0004'}),
      (d:DeclaracionJurada {ddjj_id: 'demo-0004-2022'}),
      (b:BienDeclarado {bien_id: 'demo-0004-2022-b1'}),
      (o:Organismo {organismo_id: 'org-demo-obras'}),
      (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
MERGE (p)-[:PRESENTO]->(d)
MERGE (d)-[:DECLARA]->(b)
MERGE (d)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d)-[:SEGUN_FUENTE]->(f);

// ════════════════════════════════════════════════════════════
//  CASO 5 — Declaración rectificada
// ════════════════════════════════════════════════════════════
MERGE (p:Persona {cuil: 'demo-0005'})
  SET p.nombre = 'INTENDENTE/A FICTICIO/A CINCO',
      p.cuil_parcial = 'DEMO-0005', p.provincia = 'Buenos Aires';
MERGE (d:DeclaracionJurada {ddjj_id: 'demo-0005-2023'})
  SET d.anio = 2023, d.tipo = 'Anual Rectificativa', d.rectificativa = 1,
      d.cargo = 'Intendente/a', d.sector = 'Publico',
      d.desde = '2019-12', d.proveedor_contratista = false,
      d.total_bienes = 16000000.0, d.total_deudas = 3000000.0,
      d.patrimonio_total = 16000000.0, d.patrimonio_neto = 13000000.0;
MERGE (de:Deuda {deuda_id: 'demo-0005-2023-d1'})
  SET de.tipo = 'Hipotecario', de.descripcion = 'Crédito hipotecario',
      de.importe = 3000000.0, de.periodo = 'cierre', de.clasificacion = 'Comun';
MATCH (p:Persona {cuil: 'demo-0005'}),
      (d:DeclaracionJurada {ddjj_id: 'demo-0005-2023'}),
      (de:Deuda {deuda_id: 'demo-0005-2023-d1'}),
      (o:Organismo {organismo_id: 'org-demo-municipio'}),
      (f:FuenteDocumento {doc_id: 'demo-fuente-ddjj'})
MERGE (p)-[:PRESENTO]->(d)
MERGE (d)-[:REGISTRA_DEUDA]->(de)
MERGE (d)-[:CARGO_DECLARADO_EN]->(o)
MERGE (d)-[:SEGUN_FUENTE]->(f);
