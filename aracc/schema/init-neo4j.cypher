// ============================================================
//  ar-acc — Argentina Transparency Graph
//  Esquema Neo4j: constraints e índices
//  Aplicar en la inicialización de la base de datos.
// ============================================================

// ── Constraints de unicidad (nodos principales) ────────────
CREATE CONSTRAINT persona_cuil_unique IF NOT EXISTS
  FOR (p:Persona) REQUIRE p.cuil IS UNIQUE;

CREATE CONSTRAINT empresa_cuit_unique IF NOT EXISTS
  FOR (e:Empresa) REQUIRE e.cuit IS UNIQUE;

CREATE CONSTRAINT funcionario_id_unique IF NOT EXISTS
  FOR (f:Funcionario) REQUIRE f.funcionario_id IS UNIQUE;

CREATE CONSTRAINT organismo_id_unique IF NOT EXISTS
  FOR (o:Organismo) REQUIRE o.organismo_id IS UNIQUE;

CREATE CONSTRAINT contrato_id_unique IF NOT EXISTS
  FOR (c:Contrato) REQUIRE c.contrato_id IS UNIQUE;

CREATE CONSTRAINT licitacion_id_unique IF NOT EXISTS
  FOR (l:Licitacion) REQUIRE l.licitacion_id IS UNIQUE;

CREATE CONSTRAINT cargo_id_unique IF NOT EXISTS
  FOR (c:Cargo) REQUIRE c.cargo_id IS UNIQUE;

CREATE CONSTRAINT partido_id_unique IF NOT EXISTS
  FOR (p:Partido) REQUIRE p.partido_id IS UNIQUE;

CREATE CONSTRAINT candidatura_id_unique IF NOT EXISTS
  FOR (c:Candidatura) REQUIRE c.candidatura_id IS UNIQUE;

CREATE CONSTRAINT aporte_id_unique IF NOT EXISTS
  FOR (a:AporteCampania) REQUIRE a.aporte_id IS UNIQUE;

CREATE CONSTRAINT ddjj_id_unique IF NOT EXISTS
  FOR (d:DeclaracionJurada) REQUIRE d.ddjj_id IS UNIQUE;

CREATE CONSTRAINT bien_id_unique IF NOT EXISTS
  FOR (b:BienDeclarado) REQUIRE b.bien_id IS UNIQUE;

CREATE CONSTRAINT sancion_id_unique IF NOT EXISTS
  FOR (s:Sancion) REQUIRE s.sancion_id IS UNIQUE;

CREATE CONSTRAINT acto_boletin_id_unique IF NOT EXISTS
  FOR (a:ActoBoletin) REQUIRE a.acto_id IS UNIQUE;

CREATE CONSTRAINT causa_judicial_id_unique IF NOT EXISTS
  FOR (c:CausaJudicial) REQUIRE c.causa_id IS UNIQUE;

CREATE CONSTRAINT domicilio_id_unique IF NOT EXISTS
  FOR (d:Domicilio) REQUIRE d.domicilio_id IS UNIQUE;

CREATE CONSTRAINT fuente_documento_id_unique IF NOT EXISTS
  FOR (f:FuenteDocumento) REQUIRE f.doc_id IS UNIQUE;

CREATE CONSTRAINT corrida_ingesta_id_unique IF NOT EXISTS
  FOR (c:CorridaIngesta) REQUIRE c.corrida_id IS UNIQUE;

CREATE CONSTRAINT investigacion_id_unique IF NOT EXISTS
  FOR (i:Investigacion) REQUIRE i.id IS UNIQUE;

CREATE CONSTRAINT usuario_email_unique IF NOT EXISTS
  FOR (u:Usuario) REQUIRE u.email IS UNIQUE;

// ── Índices: Persona ───────────────────────────────────────
CREATE INDEX persona_nombre IF NOT EXISTS
  FOR (p:Persona) ON (p.nombre);

CREATE INDEX persona_dni IF NOT EXISTS
  FOR (p:Persona) ON (p.dni);

// Búsqueda en modo público sobre identificador enmascarado.
CREATE INDEX persona_cuil_parcial IF NOT EXISTS
  FOR (p:Persona) ON (p.cuil_parcial);

CREATE INDEX persona_provincia IF NOT EXISTS
  FOR (p:Persona) ON (p.provincia);

// ── Índices: Empresa ───────────────────────────────────────
CREATE INDEX empresa_razon_social IF NOT EXISTS
  FOR (e:Empresa) ON (e.razon_social);

CREATE INDEX empresa_estado_afip IF NOT EXISTS
  FOR (e:Empresa) ON (e.estado_afip);

CREATE INDEX empresa_actividad_clae IF NOT EXISTS
  FOR (e:Empresa) ON (e.actividad_clae);

// ── Índices: Organismo ─────────────────────────────────────
CREATE INDEX organismo_nombre IF NOT EXISTS
  FOR (o:Organismo) ON (o.nombre);

CREATE INDEX organismo_jurisdiccion IF NOT EXISTS
  FOR (o:Organismo) ON (o.jurisdiccion);

CREATE INDEX organismo_nivel IF NOT EXISTS
  FOR (o:Organismo) ON (o.nivel);

// ── Índices: Contrato / Licitación ─────────────────────────
CREATE INDEX contrato_monto IF NOT EXISTS
  FOR (c:Contrato) ON (c.monto);

CREATE INDEX contrato_fecha IF NOT EXISTS
  FOR (c:Contrato) ON (c.fecha);

CREATE INDEX contrato_objeto IF NOT EXISTS
  FOR (c:Contrato) ON (c.objeto);

CREATE INDEX contrato_modalidad IF NOT EXISTS
  FOR (c:Contrato) ON (c.modalidad);

CREATE INDEX licitacion_fecha_apertura IF NOT EXISTS
  FOR (l:Licitacion) ON (l.fecha_apertura);

CREATE INDEX licitacion_modalidad IF NOT EXISTS
  FOR (l:Licitacion) ON (l.modalidad);

// ── Índices: Cargo / Funcionario ───────────────────────────
CREATE INDEX cargo_denominacion IF NOT EXISTS
  FOR (c:Cargo) ON (c.denominacion);

CREATE INDEX funcionario_nombre IF NOT EXISTS
  FOR (f:Funcionario) ON (f.nombre);

// ── Índices: electoral ─────────────────────────────────────
CREATE INDEX partido_nombre IF NOT EXISTS
  FOR (p:Partido) ON (p.nombre);

CREATE INDEX candidatura_anio IF NOT EXISTS
  FOR (c:Candidatura) ON (c.anio);

CREATE INDEX aporte_fecha IF NOT EXISTS
  FOR (a:AporteCampania) ON (a.fecha);

CREATE INDEX aporte_monto IF NOT EXISTS
  FOR (a:AporteCampania) ON (a.monto);

// ── Índices: DDJJ patrimoniales ────────────────────────────
CREATE INDEX ddjj_anio IF NOT EXISTS
  FOR (d:DeclaracionJurada) ON (d.anio);

CREATE INDEX ddjj_patrimonio_total IF NOT EXISTS
  FOR (d:DeclaracionJurada) ON (d.patrimonio_total);

CREATE INDEX bien_tipo IF NOT EXISTS
  FOR (b:BienDeclarado) ON (b.tipo);

CREATE INDEX bien_valor IF NOT EXISTS
  FOR (b:BienDeclarado) ON (b.valor);

// ── Índices: Sanción / Boletín / Justicia ──────────────────
CREATE INDEX sancion_tipo IF NOT EXISTS
  FOR (s:Sancion) ON (s.tipo);

CREATE INDEX sancion_fecha_inicio IF NOT EXISTS
  FOR (s:Sancion) ON (s.fecha_inicio);

CREATE INDEX acto_boletin_fecha IF NOT EXISTS
  FOR (a:ActoBoletin) ON (a.fecha);

CREATE INDEX acto_boletin_tipo IF NOT EXISTS
  FOR (a:ActoBoletin) ON (a.tipo);

CREATE INDEX causa_judicial_caratula IF NOT EXISTS
  FOR (c:CausaJudicial) ON (c.caratula);

// ── Índices: Domicilio (clave para clústeres por dirección) ─
CREATE INDEX domicilio_normalizado IF NOT EXISTS
  FOR (d:Domicilio) ON (d.direccion_normalizada);

CREATE INDEX domicilio_localidad IF NOT EXISTS
  FOR (d:Domicilio) ON (d.localidad_id);

// ── Índices: trazabilidad / auditoría ──────────────────────
CREATE INDEX fuente_documento_source_id IF NOT EXISTS
  FOR (f:FuenteDocumento) ON (f.source_id);

CREATE INDEX fuente_documento_captura IF NOT EXISTS
  FOR (f:FuenteDocumento) ON (f.fecha_captura);

CREATE INDEX corrida_ingesta_source_id IF NOT EXISTS
  FOR (c:CorridaIngesta) ON (c.source_id);

CREATE INDEX corrida_ingesta_estado IF NOT EXISTS
  FOR (c:CorridaIngesta) ON (c.estado);

// ── Índices sobre relaciones con vigencia temporal ─────────
CREATE INDEX socio_de_desde IF NOT EXISTS
  FOR ()-[r:SOCIO_DE]-() ON (r.desde);

CREATE INDEX ocupa_desde IF NOT EXISTS
  FOR ()-[r:OCUPA]-() ON (r.desde);

CREATE INDEX adjudicataria_fecha IF NOT EXISTS
  FOR ()-[r:ADJUDICATARIA_DE]-() ON (r.fecha);

// ── Índice fulltext de búsqueda global ─────────────────────
CREATE FULLTEXT INDEX entidad_busqueda IF NOT EXISTS
  FOR (n:Persona|Empresa|Funcionario|Organismo|Contrato|Licitacion|Partido|Candidatura|Sancion|ActoBoletin|CausaJudicial)
  ON EACH [n.nombre, n.razon_social, n.cuit, n.cuil_parcial, n.dni,
           n.objeto, n.denominacion, n.caratula, n.titulo, n.descripcion];
