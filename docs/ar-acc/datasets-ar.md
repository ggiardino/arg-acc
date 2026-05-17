# ar-acc — Catálogo de datasets argentinos

Todas las fuentes son **públicas y oficiales**, accesibles bajo la Ley
27.275 de Acceso a la Información Pública. El registro declarativo vive
en [`aracc/etl/sources.yml`](../../aracc/etl/sources.yml); este documento
explica el *cómo*.

> **Estados:** `loaded` (íntegro) · `partial` (subconjunto) ·
> `stale` (desactualizado) · `blocked` (bloqueo de acceso) ·
> `not_built` (pipeline pendiente — **contribuciones bienvenidas**).

---

## Nacionales

### datos.gob.ar — Portal Nacional de Datos Abiertos
- **Qué:** catálogo federal CKAN con cientos de datasets de todos los
  ministerios.
- **Cómo obtenerlo:** API CKAN REST (`/api/3/action/package_search`).
  El pipeline `datos_gob_ar` indexa el catálogo y registra cada recurso
  como `FuenteDocumento` para que el resto de pipelines resuelvan URLs.
- **Actualización:** se reindexar el catálogo a diario; cada dataset
  tiene su propia cadencia.

### COMPR.AR — Compras públicas nacionales
- **Qué:** órdenes de compra y contratos de bienes y servicios de la
  Administración Pública Nacional. Alimenta `Contrato`, `Licitacion`,
  `Organismo`, `Empresa`.
- **Cómo:** descarga de datasets publicados (también replicados en
  datos.gob.ar) + portal `comprar.gob.ar`. `scripts/download_comprar.py`
  baja los CSV a `data/comprar/raw/`.
- **Actualización:** mensual (ingesta incremental con `--since`).

### CONTRAT.AR — Obra pública nacional
- **Qué:** procesos y contratos de obra pública. Igual modelo que COMPR.AR.
- **Cómo:** portal `contratar.gob.ar` + CSV. **Estado:** `not_built`.

### Declaraciones Juradas Patrimoniales — Oficina Anticorrupción
- **Qué:** patrimonio de funcionarios bajo la Ley 25.188 de Ética en el
  Ejercicio de la Función Pública. Alimenta `DeclaracionJurada`,
  `BienDeclarado` y la regla de enriquecimiento patrimonial.
- **Cómo:** datasets publicados por la OA y/o solicitud formal de acceso
  a la información. **Sensible** — ver consideraciones legales.
- **Actualización:** anual.

### AFIP / ARCA — Padrón CUIT y estados administrativos
- **Qué:** existencia y estado de personas y empresas, actividad
  económica (CLAE), domicilio fiscal. Da consistencia a `Persona` y
  `Empresa` y permite validar el dígito verificador del CUIT/CUIL.
- **Cómo:** servicio de constancia de inscripción (API) y padrones
  publicados. **Estado:** `not_built`.

### Boletín Oficial (BORA)
- **Qué:** designaciones de funcionarios, contrataciones, constitución
  de sociedades, sanciones, normas. Alimenta `ActoBoletin`, `Cargo`,
  `Sancion`.
- **Cómo:** API de BORA / parsing estructurado de las secciones diarias.
- **Actualización:** diaria.

### Cámara Nacional Electoral — Candidaturas y aportes
- **Qué:** candidatos por elección, afiliaciones partidarias, aportes y
  financiamiento de campañas (Ley 26.215). Alimenta `Candidatura`,
  `Partido`, `AporteCampania`.
- **Cómo:** datasets de la CNE / datos.gob.ar. **Estado:** `not_built`.

### Presupuesto Abierto
- **Qué:** crédito, devengado y pagado por jurisdicción y programa.
  Aporta contexto de magnitud a contratos y organismos.
- **Cómo:** API SICI de Presupuesto Abierto.
- **Actualización:** mensual.

### API Georef — Normalización geográfica
- **Qué:** normaliza provincias, departamentos, municipios, localidades
  y calles; geocoding de domicilios. Clave para los clústeres por
  domicilio compartido (`Domicilio`).
- **Cómo:** API REST pública (`apis.datos.gob.ar/georef/api`).

### Datos de Justicia
- **Qué:** causas, sentencias, registro de deudores alimentarios y otros
  datasets del portal `datos.jus.gob.ar`. Alimenta `CausaJudicial`.
- **Cómo:** datasets / API. **Estado:** `not_built`.

### Portal de Transparencia del Estado
- **Qué:** audiencias de gestión de intereses, viajes oficiales,
  registro de obsequios. Refuerza las señales de conflicto de interés.

---

## Subnacionales (federalismo)

Argentina es federal: las compras provinciales y municipales son una
porción enorme del gasto. `ar-acc` modela cada jurisdicción como un
`Organismo` con `nivel` (`nacional`/`provincial`/`municipal`).

| Jurisdicción | Portal | Estado |
|--------------|--------|--------|
| CABA | Buenos Aires Compras (BAC) / `data.buenosaires.gob.ar` | `not_built` |
| Provincia de Buenos Aires | PBA Compra (PBAC) | `not_built` |
| Córdoba, Santa Fe, Mendoza, ... | portales provinciales propios | `not_built` |

Cada provincia es una contribución acotada e ideal para empezar: nuevo
módulo en `pipelines/provincial/`, fila en `sources.yml`, fixture y test.

---

## Cómo se mantienen actualizados

1. **Scheduling con Prefect** (`aracc/etl/flows.py`): flujos diario y
   mensual según la cadencia de cada fuente.
2. **Ingesta incremental:** los pipelines aceptan `--since YYYY-MM-DD`
   para procesar solo registros nuevos.
3. **Idempotencia:** claves naturales (CUIT/CUIL) + `MERGE` — re-ejecutar
   nunca duplica ni corrompe.
4. **Auditoría:** cada corrida deja un nodo `CorridaIngesta` con estado y
   métricas; `docs/pipeline_status.md` se genera a partir de ellos.
