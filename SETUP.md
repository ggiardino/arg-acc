# ar-acc — Guía de instalación y uso

**ar-acc** es una réplica argentina y ligera del framework *acc/bro* de OCCRP
para investigación de corrupción. Permite consultar un grafo de Neo4j en
lenguaje natural usando un agente de IA (RAG sobre grafos).

Funciona **sin Docker**: solo necesitás Python y una base Neo4j (local o en la
nube). Soporta dos modos de uso:

- **Local:** dashboard interactivo con Streamlit.
- **Nube:** despliegue serverless en Vercel (FastAPI + frontend integrado).

---

## 1. Requisitos previos

1. **Python 3.10 o superior** instalado y agregado al `PATH`.
   Verificalo con: `python --version`
2. **Una base de datos Neo4j**, en cualquiera de estas dos modalidades:
   - **Neo4j Desktop** (local): creá una base y anotá usuario y contraseña.
     La URI suele ser `bolt://localhost:7687`.
   - **Neo4j Aura** (nube, gratis): creá una instancia en
     <https://neo4j.com/cloud/aura/>. Te dará una URI del tipo
     `neo4j+s://xxxxxxxx.databases.neo4j.io`.
3. **Una API Key** de al menos uno de estos proveedores de IA:
   - OpenAI — <https://platform.openai.com/api-keys>
   - Groq — <https://console.groq.com/keys> (rápido y con capa gratuita)
   - Anthropic — <https://console.anthropic.com/>

---

## 2. Configurar el archivo `.env`

En la **raíz del proyecto** creá un archivo llamado `.env` (sin extensión) con
este contenido. Completá solo los valores que vayas a usar:

```env
# --- Conexión a Neo4j -------------------------------------------------------
# Local (Neo4j Desktop):
NEO4J_URI=bolt://localhost:7687
# En la nube (Neo4j Aura), reemplazá por tu URI:
# NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=tu_password_de_neo4j
NEO4J_DATABASE=neo4j

# --- API Keys de los proveedores de IA --------------------------------------
# Pegá tu clave real a la derecha del signo "=" en al menos una de estas
# variables (la que corresponda al proveedor elegido en LLM_PROVIDER).
# Dejá vacías las que no uses.
OPENAI_API_KEY=
GROQ_API_KEY=
ANTHROPIC_API_KEY=

# --- Selector de proveedor y modelo -----------------------------------------
# Opciones válidas: openai | groq | anthropic
LLM_PROVIDER=groq
OPENAI_MODEL=gpt-4o-mini
GROQ_MODEL=llama-3.3-70b-versatile
ANTHROPIC_MODEL=claude-sonnet-4-6
```

> El proveedor y la API Key también se pueden cambiar en caliente desde la
> barra lateral del dashboard o desde la interfaz web, sin tocar el `.env`.

---

## 3. Ejecución local en Windows (recomendado)

Con el `.env` ya configurado, hacé **doble clic** sobre `run_local.bat`
(o ejecutalo desde la terminal). El script automáticamente:

1. Crea el entorno virtual `venv` si no existe.
2. Instala todas las dependencias de `requirements.txt`.
3. Ejecuta la ingesta y puebla Neo4j con el dataset de prueba.
4. Levanta el dashboard de Streamlit en el navegador.

```bat
run_local.bat
```

El dashboard queda disponible en <http://localhost:8501>.

### Ejecución manual (alternativa, cualquier sistema operativo)

```bash
python -m venv venv
venv\Scripts\activate            # En Windows
# source venv/bin/activate       # En Linux / macOS

pip install -r requirements.txt
python -m pipelines.import_to_neo4j
streamlit run web/app_streamlit.py
```

---

## 4. Despliegue serverless en Vercel (opcional)

1. Subí el repositorio a GitHub e importalo en <https://vercel.com>.
2. En **Settings → Environment Variables** cargá las mismas variables del
   `.env` (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, las API Keys y
   `LLM_PROVIDER`). Para la nube conviene usar **Neo4j Aura**.
3. El archivo `vercel.json` ya redirige todas las rutas a `api/index.py`.
4. Desplegá. La interfaz web quedará disponible en la URL del proyecto y el
   endpoint de consultas en `POST /api/chat`.

> Antes de usar la web, asegurate de haber poblado Neo4j al menos una vez con
> `python -m pipelines.import_to_neo4j` apuntando a la base de Aura.

---

## 5. Preguntas de auditoría que el agente puede resolver

El dataset simulado modela funcionarios, sus viajes al exterior, empresas y
las licitaciones que ganaron. Probá con estas tres consultas complejas:

1. **Patrimonio desproporcionado + viajes al exterior**
   > ¿Qué funcionarios tienen un patrimonio desproporcionado respecto de sus
   > ingresos y a qué destinos del exterior viajaron?

2. **Concentración de contratos del Estado**
   > ¿Qué empresas ganaron más de un contrato del Estado y cuál es el monto
   > total adjudicado a cada una?

3. **Viajes a paraísos fiscales**
   > ¿Qué funcionarios viajaron a paraísos fiscales como las Islas Caimán o
   > Andorra y cuál es su cargo?

El agente traduce automáticamente estos conceptos cotidianos
("empleados públicos", "vuelos al exterior", "obras del Estado") a las
etiquetas y relaciones del grafo (`Funcionario`, `VIAJO_A`, `GANO_CONTRATO`).

---

## 6. Dashboard de inconsistencias en Declaraciones Juradas

Además del chat, ar-acc incluye un **dashboard estilo terminal** navegable por
secciones jerárquicas que detecta inconsistencias en las Declaraciones Juradas
Patrimoniales Integrales (Ley 25.188). Se abre en **`/dashboard`** (hay un
botón en la página principal).

Para levantarlo localmente en Windows, hacé doble clic en **`run_dashboard.bat`**
y abrí <http://localhost:8000/dashboard>. En la nube (Vercel) queda disponible
directamente en `tu-proyecto.vercel.app/dashboard`.

> **Importante:** cada hallazgo es una **hipótesis a verificar** contra la
> fuente oficial citada. No constituye prueba ni imputación. Rige la
> presunción de inocencia.

### Cómo se navega

Secciones: `organismos` · `personas` · `inconsistencias`. Se recorre con el
teclado (`↑`/`↓` mover, `Enter` abrir, `←` subir) o con comandos: `ls`,
`cd N`, `cd ..`, `find TEXTO`, `help`.

### Detectores incluidos

| Detector | Qué marca |
|---|---|
| Salto patrimonial | El patrimonio declarado crece +50% entre dos DDJJ consecutivas |
| Descuadre interno | El total de bienes no coincide con la suma de los bienes individuales |
| Funcionario-proveedor | La persona se declara proveedora del Estado mientras ejerce un cargo |
| Años faltantes | Hay años intermedios sin DDJJ presentada |
| Rectificativa | La declaración fue rectificada después de presentada |

### Opción A — Cargar datos públicos REALES

El cargador toma las DDJJ del portal oficial de la Justicia Argentina
(`datos.jus.gob.ar`):

```bash
# Descarga automática del año (requiere salida a internet):
python pipelines/import_ddjj_real.py --anio 2023

# Si tu red bloquea el portal: descargá los CSV del dataset manualmente desde
# https://datos.jus.gob.ar/dataset/declaraciones-juradas-patrimoniales-integrales
# dejalos en data/ddjj/raw/ y luego corré:
python pipelines/import_ddjj_real.py --anio 2023 --offline
```

Cargá varios años (`--anio 2022`, `--anio 2023`, …) para que el detector de
salto patrimonial pueda comparar declaraciones consecutivas.

### Opción B — Datos de demostración (previsualizar la UI)

Para ver el dashboard funcionando ya, sin esperar la ingesta real, aplicá el
grafo sintético de demo (datos ficticios, ninguna persona es real):

```bash
cypher-shell -u neo4j -p TU_PASSWORD -f dashboard/seed_demo.cypher
```

Reproduce los 5 detectores con legisladores ficticios.

---

## 7. Estructura del proyecto

```
ar-acc/
├── requirements.txt              # Dependencias Python
├── vercel.json                   # Ruteo serverless hacia api/index.py
├── run_local.bat                 # Arranque automatizado en Windows
├── SETUP.md                      # Esta guía
├── agent.py                      # Capa de IA (GraphCypherQAChain)
├── config/
│   └── settings.py               # Configuración centralizada (.env)
├── pipelines/
│   ├── import_to_neo4j.py        # Ingesta del dataset simulado (chat)
│   └── import_ddjj_real.py       # Ingesta de DDJJ reales (dashboard)
├── dashboard/
│   ├── service.py                # Motor de detección de inconsistencias
│   ├── web.py                    # Rutas FastAPI del dashboard
│   ├── terminal.html             # Interfaz web estilo terminal
│   └── seed_demo.cypher          # Grafo sintético de demostración
├── web/
│   └── app_streamlit.py          # Dashboard local interactivo
└── api/
    └── index.py                  # FastAPI + frontend + dashboard
```

---

## 8. Solución de problemas

| Síntoma | Causa probable / Solución |
|---|---|
| `No se pudo conectar a Neo4j` | Revisá `NEO4J_URI`, usuario y contraseña en `.env`. En Aura usá el prefijo `neo4j+s://`. |
| `Falta la API Key '...'` | Cargá la key en el `.env` o pegala en la barra lateral / interfaz web. |
| El grafo aparece vacío | Ejecutá `python -m pipelines.import_to_neo4j` (chat) o `python pipelines/import_ddjj_real.py --anio 2023` (dashboard). |
| El dashboard dice "ERROR DE CONEXIÓN" | Neo4j no está activo o el `.env` apunta mal. |
| No se pudo descargar del portal oficial | Descargá los CSV a mano y usá `--offline` (ver sección 6). |
| `python` no se reconoce | Instalá Python 3.10+ y marcá "Add to PATH" durante la instalación. |
