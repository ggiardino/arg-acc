// ============================================================
//  ar-acc — Grafo de demostración (datos SINTÉTICOS)
//
//  Datos ficticios para probar el grafo y las queries de detección
//  sin descargar fuentes reales. NINGUNA persona o empresa aquí es
//  real; cualquier coincidencia con la realidad es casual.
//
//  Aplicar después del esquema:
//    cypher-shell ... --file /schema/seed-demo.cypher
//
//  Idempotente (usa MERGE): se puede re-aplicar sin duplicar.
//  Cada sentencia (terminada en ;) es autónoma: re-MATCHea los nodos
//  que necesita, porque las variables no persisten entre sentencias.
// ============================================================

// ── Nodos ───────────────────────────────────────────────────

MERGE (src:FuenteDocumento {doc_id: 'demo-fuente'})
  SET src.source_id = 'demo',
      src.url = 'https://ejemplo.local/demo',
      src.fecha_captura = '2024-01-01';

MERGE (org:Organismo {organismo_id: 'org-min-infraestructura'})
  SET org.nombre = 'Ministerio de Infraestructura (DEMO)',
      org.jurisdiccion = 'Nacional', org.nivel = 'nacional';

MERGE (dom:Domicilio {domicilio_id: 'dom-demo-1'})
  SET dom.direccion_normalizada = 'AV SIEMPREVIVA 742, CABA',
      dom.localidad_id = 'caba-01';

// Funcionario público con participación societaria (conflicto).
MERGE (juan:Persona {cuil: '20111111112'})
  SET juan.nombre = 'GOMEZ JUAN CARLOS',
      juan.cuil_parcial = '20-XXXXXX11-2',
      juan.provincia = 'CABA';

// Apoderada de dos empresas distintas (señal: mismo apoderado).
MERGE (maria:Persona {cuil: '27999999994'})
  SET maria.nombre = 'PEREZ MARIA',
      maria.cuil_parcial = '27-XXXXXX99-4';

MERGE (sur:Empresa {cuit: '30111111113'})
  SET sur.razon_social = 'CONSTRUCTORA DEL SUR SA (DEMO)',
      sur.estado_afip = 'ACTIVO', sur.actividad_clae = '410011';

MERGE (norte:Empresa {cuit: '30222222224'})
  SET norte.razon_social = 'VIALIDAD NORTE SA (DEMO)',
      norte.estado_afip = 'ACTIVO', norte.actividad_clae = '421000';

MERGE (cargo:Cargo {cargo_id: 'cargo-demo-1'})
  SET cargo.denominacion = 'Director de Compras';

MERGE (func:Funcionario {funcionario_id: 'func-demo-juan'})
  SET func.nombre = 'GOMEZ JUAN CARLOS';

MERGE (pt:Partido {partido_id: 'partido-demo-1'})
  SET pt.nombre = 'FRENTE DEMOSTRACION (DEMO)';

// Declaraciones Juradas: patrimonio sube de 10M a 28M (+180%).
MERGE (dj1:DeclaracionJurada {ddjj_id: 'ddjj-demo-2022'})
  SET dj1.anio = 2022, dj1.fecha = '2022-09-30',
      dj1.patrimonio_total = 10000000.0, dj1.tipo = 'Anual';

MERGE (dj2:DeclaracionJurada {ddjj_id: 'ddjj-demo-2023'})
  SET dj2.anio = 2023, dj2.fecha = '2023-09-30',
      dj2.patrimonio_total = 28000000.0, dj2.tipo = 'Anual';

MERGE (bien:BienDeclarado {bien_id: 'bien-demo-1'})
  SET bien.tipo = 'Inmueble', bien.valor = 22000000.0,
      bien.descripcion = 'Inmueble declarado 2023';

MERGE (lic:Licitacion {licitacion_id: 'lic-demo-1'})
  SET lic.modalidad = 'LICITACION_PUBLICA', lic.fecha_apertura = '2023-01-10';

// ── Relaciones ──────────────────────────────────────────────

// Empresas en el mismo domicilio (señal: misma dirección).
MATCH (sur:Empresa {cuit: '30111111113'}),
      (norte:Empresa {cuit: '30222222224'}),
      (dom:Domicilio {domicilio_id: 'dom-demo-1'})
MERGE (sur)-[:TIENE_DOMICILIO]->(dom)
MERGE (norte)-[:TIENE_DOMICILIO]->(dom);

// Vínculo funcionario -> cargo -> organismo.
MATCH (juan:Persona {cuil: '20111111112'}),
      (func:Funcionario {funcionario_id: 'func-demo-juan'}),
      (cargo:Cargo {cargo_id: 'cargo-demo-1'}),
      (org:Organismo {organismo_id: 'org-min-infraestructura'})
MERGE (juan)-[:ES_FUNCIONARIO]->(func)
MERGE (func)-[oc:OCUPA]->(cargo)
  SET oc.desde = '2020-01-01', oc.hasta = null
MERGE (cargo)-[:EN]->(org);

// Participación societaria y apoderamientos.
MATCH (juan:Persona {cuil: '20111111112'}),
      (maria:Persona {cuil: '27999999994'}),
      (sur:Empresa {cuit: '30111111113'}),
      (norte:Empresa {cuit: '30222222224'})
MERGE (juan)-[soc:SOCIO_DE]->(sur)
  SET soc.pct = 60.0, soc.rol = 'Socio gerente',
      soc.desde = '2018-01-01', soc.hasta = null
MERGE (maria)-[:APODERADO_DE]->(sur)
MERGE (maria)-[:APODERADO_DE]->(norte);

// Declaraciones juradas presentadas + bien declarado.
MATCH (juan:Persona {cuil: '20111111112'}),
      (dj1:DeclaracionJurada {ddjj_id: 'ddjj-demo-2022'}),
      (dj2:DeclaracionJurada {ddjj_id: 'ddjj-demo-2023'}),
      (bien:BienDeclarado {bien_id: 'bien-demo-1'})
MERGE (juan)-[:PRESENTO]->(dj1)
MERGE (juan)-[:PRESENTO]->(dj2)
MERGE (dj2)-[:DECLARA]->(bien);

// Organismo convoca la licitación.
MATCH (org:Organismo {organismo_id: 'org-min-infraestructura'}),
      (lic:Licitacion {licitacion_id: 'lic-demo-1'})
MERGE (org)-[:CONVOCA]->(lic);

// Tres contrataciones directas del mismo organismo a la misma empresa,
// dentro del período de las DDJJ. Dispara varias reglas a la vez:
// adjudicaciones directas repetidas + conflicto de interés +
// enriquecimiento patrimonial.
MATCH (org:Organismo {organismo_id: 'org-min-infraestructura'}),
      (sur:Empresa {cuit: '30111111113'}),
      (src:FuenteDocumento {doc_id: 'demo-fuente'})
UNWIND [
  {id: 'contrato-demo-1', fecha: '2023-02-15', monto: 6000000.0},
  {id: 'contrato-demo-2', fecha: '2023-05-20', monto: 7500000.0},
  {id: 'contrato-demo-3', fecha: '2023-08-05', monto: 5200000.0}
] AS row
MERGE (c:Contrato {contrato_id: row.id})
  SET c.objeto = 'Obra vial (DEMO)', c.monto = row.monto,
      c.modalidad = 'CONTRATACION_DIRECTA', c.fecha = row.fecha,
      c.precio_unitario = row.monto
MERGE (org)-[:CONTRATA]->(c)
MERGE (sur)-[adj:ADJUDICATARIA_DE]->(c)
  SET adj.fecha = row.fecha
MERGE (c)-[:SEGUN_FUENTE]->(src);

// Aporte de campaña de un proveedor del Estado (señal de riesgo).
MATCH (sur:Empresa {cuit: '30111111113'}),
      (pt:Partido {partido_id: 'partido-demo-1'})
MERGE (sur)-[ap:APORTO]->(pt)
  SET ap.monto = 5000000.0, ap.anio = 2023, ap.fecha = '2023-06-01';

// Trazabilidad: vincular DDJJ y empresas a una fuente.
MATCH (src:FuenteDocumento {doc_id: 'demo-fuente'})
MATCH (n) WHERE n:DeclaracionJurada OR n:Empresa
MERGE (n)-[:SEGUN_FUENTE]->(src);
