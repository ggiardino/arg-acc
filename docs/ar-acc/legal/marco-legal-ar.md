# ar-acc — Marco legal y ético (Argentina)

`ar-acc` opera dentro del ordenamiento jurídico argentino. Este documento
sustituye al `LGPD.md` del proyecto brasileño original.

---

## 1. Solo datos públicos

`ar-acc` **únicamente ingiere información ya publicada oficialmente**. El
fundamento es la **Ley 27.275 de Derecho de Acceso a la Información
Pública** y su principio de *transparencia activa*: el Estado debe
publicar proactivamente información de gestión, presupuesto,
contrataciones y nóminas.

El proyecto **no**:
- accede a fuentes privadas, bases internas ni sistemas con control de
  acceso;
- elude `robots.txt`, captchas ni autenticación;
- combina datos para reidentificar a personas físicas que no ejercen
  función pública.

`ar-acc` *reproduce* dato oficial; no lo *origina*.

---

## 2. Ley 25.326 de Protección de los Datos Personales

Aunque los datos de funcionarios en ejercicio tienen un interés público
preponderante (criterio sostenido por la Agencia de Acceso a la
Información Pública), `ar-acc` aplica **minimización de datos**:

- **Modo público:** los identificadores (CUIT/CUIL/DNI) se exhiben
  **enmascarados** (`20-XXXXXX78-9`). El núcleo coincidente con el DNI
  nunca se publica.
- **Modo interno autenticado:** el identificador completo solo es
  accesible en despliegues privados, bajo control de acceso, para usos
  legítimos (periodismo de investigación, organismos de control).
- **Datos sensibles** (DDJJ patrimoniales): se cargan respetando el
  alcance de publicidad que fija la propia Ley 25.188 y la OA.
- **Datos de personas no funcionarias:** se incorporan solo cuando son
  inseparables de un hecho público (p. ej. socio de una empresa
  contratista) y siempre enmascarados en modo público.

### Derechos ARCO

Existe un canal de **rectificación y supresión** (plantilla de issue
`data_correction` / `privacy_request`). Como `ar-acc` refleja la fuente
oficial, una corrección suele requerir además corregir el origen; el
proyecto enlaza al organismo responsable y, mientras tanto, puede
suprimir o anotar el dato cuestionado.

---

## 3. Disclaimer obligatorio

Toda vista del frontend, todo export y toda respuesta de la API incluye:

> **ar-acc agrega datos públicos y muestra conexiones entre ellos. NO
> afirma la comisión de delito, falta ni irregularidad alguna. Las
> "señales de riesgo" son hipótesis estadísticas a verificar contra la
> fuente oficial citada. Pueden existir explicaciones legítimas. Rige de
> forma absoluta la presunción de inocencia (art. 18, Constitución
> Nacional).**

---

## 4. Licencia

**AGPL-3.0**, heredada de `br-acc`. Garantiza que toda mejora desplegada
como servicio de red vuelva a la comunidad. Las bases de datos
resultantes se publican bajo licencia abierta compatible con la de las
fuentes oficiales.

---

## 5. Trazabilidad como defensa

El diseño del grafo exige que **toda arista material** tenga un vínculo
`:SEGUN_FUENTE` hacia un nodo `FuenteDocumento` (URL + hash + fecha de
captura). Esto significa que cualquier afirmación de `ar-acc` puede
contrastarse con el documento oficial del que proviene: el proyecto no
sustituye a la fuente, la indexa y la conecta.

---

## 6. Uso responsable

`ar-acc` es una herramienta para **periodismo de datos, control
ciudadano y organismos de control**. No es una herramienta de
difamación, escrache ni hostigamiento. El abuso de la plataforma para
acosar a personas contradice su propósito y su licencia de uso
(`TERMS.md`). El equipo coopera con pedidos legítimos de autoridades de
aplicación y de la Agencia de Acceso a la Información Pública.
