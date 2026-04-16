# Proceso de Validación y Depuración — LineUpProcessor

> **Nota sobre dependencias en cadena:** Cada seccion corre en orden secuencial.Si un paso falla para una fila, los pasos siguientes que dependan del resultado de ese paso pueden verse afectados. Donde esto ocurre, se indica explícitamente. En general, el script intenta aislar errores para no generar falsos positivos en pasos posteriores, pero hay casos donde un fallo temprano propaga consecuencias.

---

## 1. Carga de datos

Se lee la hoja de Excel indicada, comenzando desde la fila de encabezado configurada (por defecto fila 12). Todas las columnas se cargan con tipo `object` en pandas — es decir, texto plano sin ninguna interpretación de tipos. Esto es intencional: el script hace sus propios casteos controlados en el paso siguiente.

El DataFrame se recorta al primer registro donde la columna `VESSEL` esté vacía. Todo lo que esté debajo de ese punto se descarta, asumiendo que es el fin de los datos útiles.

Opcionalmente se puede activar una verificación de encabezados contra el layout esperado.

---

## 2. Casteos, Normalizaciones y sus Efectos en Cadena

Cada columna pasa por una transformación según su tipo esperado. Si la transformación falla para un valor, ese valor queda como `None` / `NaT` en el DataFrame y se registra un **error**. Esto es importante: los pasos de validación posteriores están escritos para detectar estos `None` y evitar reportar falsos errores derivados — pero no siempre es posible cubrirlo al 100%.

### 2.1 Strings

**Aplica a:** la mayoría de columnas de texto (barcos, empresas, puertos, etc.)

**Qué hace:**
- Convierte a mayúsculas
- Elimina espacios múltiples internos (colapsa a uno solo)
- Hace `strip()` de espacios al inicio y al final
- Preserva los `NA` originales (un vacío sigue siendo vacío)

**Si falla:** No genera error. Es una transformación que no puede fallar en sí misma.

[!IMPORTANT]
TODO: Podria verificar si ej el texto antes '  ' se convierte en '', es un error o un warning, pero actualmente no se hace eso

*Efecto en cadena:* Ninguno relevante, salvo que normalizar a mayúsculas es necesario para que las comparaciones posteriores (enums, blacklist, productos) funcionen correctamente.

---

### 2.2 Fechas (`datetime`)

**Aplica a:** `DATE_OF_ARRIVAL (ATA)`, `ETB`, `ETC`

**Formato esperado:** `DD/MM/YYYY`

**Qué hace:** Intenta parsear la fecha. Si el valor no puede convertirse, queda como `NaT`.

**Si falla:** → **Error** `INVALID_VALUE`

*Efecto en cadena:* Una fecha que no pudo convertirse quedará como `NaT`. Esto impacta directamente en:
- La **validación de intervalos** (sección 5): si ATA falla, ETB y ETC no se pueden validar cronológicamente. El script detecta los índices con error de conversión y los excluye de esa validación para no generar falsos errores.
- La **validación de estados** (sección 4): las reglas de fechas futuras y fechas requeridas por status filtran los índices con error de conversión antes de correr, por la misma razón.

---

### 2.3 Decimales

**Aplica a:** `TOTAL_MT`

**Formato esperado** '1,234.56'. Separador de miles es `,` (opcional) y el separador obligatorio de decimales es `.`

**Qué hace:** Convierte el valor a `Decimal`. Si no puede convertirlo, queda como `None`.

**Si falla:** → **Error** `INVALID_VALUE`

*Efecto en cadena:* Si `TOTAL_MT` falla el casteo, quedará como `None`. Esto afecta:
- La **validación de rango de TOTAL_MT** en `_validate_cargo`: los índices con error de conversión se excluyen antes de chequear el rango, por lo que si se puso ej '123.456.789', es un numero invalido, y se saltara la validacion de su rango.
- La **comparación de suma MT_BY_PRODUCT vs TOTAL_MT**: si `TOTAL_MT` es `None` por error de conversión, esa fila se salta en la suma para no generar un falso error de discrepancia.

---

### 2.4 Enums

**Aplica a:**
- `STATUS` → `VesselStatus` — **no nullable**
- `OPERATION` → `OperationStatus` — **no nullable**
- `TYPE` → `CargoType` — nullable
- `DATE_OF_ARRIVAL_PERIOD`, `ETB_PERIOD`, `ETC_PERIOD` → `DatePeriod` — nullable

**Qué hace:** Intenta mapear el valor de texto al enum correspondiente. Si el valor no existe en el enum, queda como `None`.

**Si falla (valor inválido):** → **Error** `MISSING_VALUE` con los valores válidos esperados listados en el mensaje

**Si falla (valor nulo en columna no-nullable):** → **Error** `OUT_OF_RANGE`

*Efecto en cadena:* Si `STATUS` o `OPERATION` fallan el casteo, quedan como `None`. Esto afecta directamente la **validación de estados** (sección 4):
- Las reglas de combinación `VesselStatus` + `OperationStatus` excluyen filas donde cualquiera de los dos tuvo error de conversión.
- Las reglas de fechas requeridas por status también excluyen estos índices.

Si `TYPE` falla, afecta la **validación de carga** (sección 3): la validación de producto vs tipo de carga excluye filas donde `TYPE` tuvo error, para no reportar productos inválidos por una razón que ya fue reportada.

Si los `PERIOD` fallan, afecta la **validación de intervalos** (sección 5).

---

### 2.5 Puerto y País (`PORT_LOAD_DISCH`)

**Qué hace:** Espera un valor con un separador (`/`, `-`, `+`, `,`) que divida el puerto del país. Lo reformatea como `Puerto, País`.

**Si falla (no hay separador):** → **Error** `INVALID_FORMAT`, el valor queda como `None`

[!IMPORTANT]
Se puedo cambiar eso a un warning, y que no afecte al generar el informe

*Efecto en cadena:* Solo afecta visualización. No impacta otras validaciones.

---

### 2.6 Terminal

**Qué hace:** Verifica que el valor esté dentro de la lista de terminales válidas para ese puerto. Se corre solo si hay terminales configuradas.

**Si falla:** → **Error** `INVALID_VALUE`. El valor **no se reemplaza** (se conserva el original en el DataFrame).

**Efecto en cadena:** Ninguno relevante hacia otros pasos.

---

### 2.7 PIER

**Qué hace:** Elimina todos los espacios internos del valor (no solo los extremos).

**Si falla:** No genera error.

---

## 3. Validación de Carga (`_validate_cargo`)

Esta sección valida la coherencia entre las columnas `TYPE`, `PRODUCT`, `MT_BY_PRODUCT` y `TOTAL_MT`. Es importante tener en cuenta que `PRODUCT` y `MT_BY_PRODUCT` pueden contener **múltiples valores separados** por `/`, `-`, `+` o `;` (ej: `COAL/IRON` y `5000/3000`).

[!IMPORTANT]
Como los pesos no pueden ser negativos, el separador - es valido para las columnas numericas

> **Dependencia de entrada:** Esta sección depende de que `TYPE` y `TOTAL_MT` hayan sido casteados correctamente. Si alguno tuvo error de conversión, los pasos que los involucran filtran esos índices antes de correr.

### Paso 1 — Producto sin Type

Si `PRODUCT` tiene valor pero `TYPE` es `None` (y no fue por error de conversión), se reporta que el producto no tiene un tipo válido asociado.

→ **Error** `MISSING_VALUE`

---

### Paso 2 — NA cruzado: MT_BY_PRODUCT / TOTAL_MT

Si una de las dos columnas tiene valor pero la otra está vacía, se reporta la que está vacía.

→ **Error** `MISSING_VALUE`

> **Dependencia:** Si `TOTAL_MT` tuvo error de conversión, esos índices se excluyen de esta regla para no reportarlo dos veces.

---

### Paso 3 — Cantidad de productos ≠ cantidad de MTs

Si al separar por delimitador, `PRODUCT` tiene 2 partes pero `MT_BY_PRODUCT` tiene 3 (o cualquier discrepancia), se reporta.

→ **Warning** `SUSPICIOUS_VALUE` nivel **HIGH**

---

### Paso 4 — TOTAL_MT fuera de rango

`TOTAL_MT` debe estar en el rango `(0, 300.000)` exclusivo.

→ **Error** `INVALID_VALUE`

> **Efecto en cadena:** Si `TOTAL_MT` falla aquí, esa fila se excluye de la comparación de suma del paso 6.

---

### Paso 5 — MT_BY_PRODUCT: casteo a Decimal y rango por elemento

Cada parte individual de `MT_BY_PRODUCT` (después de separar) se convierte a `Decimal`. Si alguna parte no es decimal o está fuera de rango `(0, 300.000)`, se reporta sobre el valor original completo de la columna.

[!IMPORTANT]
TODO: Aunque verificar el rango por partes no es necesario, ya verifico que TOTAL_MT <300_00 y posteriormente verifico que sum(MT_BY_PRODUCT) == TOTAL_MT y si TOTAL_MT <300_000 -> sum(MT_BY_PRODUCT) < 300_000 (y esta parte puede mejorar performance por que es un apply chambon) 
TODO: Verificar que 0<MT_BY_PRODUCT<300_000 omite que deberia ser 0<MT_BY_PRODUCT/x<300_000/x , siendo x la cantidad de productos que trae la motonave (si trae dos productos, cada producto debe max 150_000)
(Tocaria dividir en base al conteo de valores unicos del indice de la serie explotada)

→ **Error** `INVALID_VALUE` (no-decimal o fuera de rango)

> **Efecto en cadena:** Si algún elemento falla aquí, esa fila se excluye de la comparación de suma del paso 6.

---

### Paso 6 — Suma de MT_BY_PRODUCT vs TOTAL_MT

Se suman todos los elementos de `MT_BY_PRODUCT` por fila y se compara con `TOTAL_MT`. Hay dos escenarios:

| Diferencia | Qué se reporta |
|---|---|
| ≤ 20% | Error solo en `MT_BY_PRODUCT` |
| > 20% | Error en `MT_BY_PRODUCT` **y** en `TOTAL_MT` |

→ **Error** `INVALID_VALUE` en uno o ambos campos según el margen

> **Dependencia:** Solo se corre en filas donde ni `MT_BY_PRODUCT` ni `TOTAL_MT` tuvieron problemas en pasos anteriores (conversión, rango, conteo).

---

### Paso 7 — Producto válido para el CargoType

Cada producto individual se verifica contra el diccionario de productos permitidos para ese `CargoType`. Si el producto no está en la lista permitida para ese tipo de carga, se reporta.

→ **Warning** `SUSPICIOUS_VALUE` nivel **MEDIUM**

> **Dependencia:** Se excluyen filas donde `TYPE` fue `None` ya sea por estar vacío o por error de conversión.

---

### Resultado final de esta sección

- Las filas con errores en `PRODUCT` o `MT_BY_PRODUCT` quedan con esos campos en `None`.
- Las filas válidas tienen `PRODUCT` reformateado (`/` como separador estándar) y `MT_BY_PRODUCT` con los decimales normalizados.
- Si `MT_BY_PRODUCT` quedó vacío pero `TOTAL_MT` tiene valor, se asume `MT_BY_PRODUCT = TOTAL_MT` como fallback (se registra en log como warning, no como error reportado).

---

## 4. Validación de Estados (`_validate_status`)

Esta sección valida la coherencia entre el `STATUS` del buque, su `OPERATION`, y las fechas asociadas.

> **Dependencia de entrada:** Depende de que `STATUS`, `OPERATION`, `ETB`, `ETC` y `DATE_OF_ARRIVAL` hayan sido casteados. Los índices con error de conversión en cualquiera de estas columnas se excluyen de las reglas que los involucran.

### Paso 1 — BERTHED requiere ETB

Si el status es `BERTHED` y `ETB` está vacía (y no fue por error de conversión de ETB), se reporta.

→ **Error** `MISSING_VALUE` en `ETB`

---

### Paso 2 — SAILED requiere ETC

Si el status es `SAILED` y `ETC` está vacía (y no fue por error de conversión de ETC), se reporta.

→ **Error** `MISSING_VALUE` en `ETC`

---

### Paso 3 — Fechas futuras en status distintos a ANNOUNCED

Para cualquier status que no sea `ANNOUNCED`, las fechas `ATA`, `ETB` y `ETC` no pueden ser futuras respecto a la fecha actual.

→ **Error** `OUT_OF_RANGE`

> **Dependencia:** Se excluyen filas con errores de conversión en `STATUS`. Las fechas que fallaron conversión quedaron como `NaT`, por lo que no pueden ser "futuras" — no se reportan aquí.

---

### Paso 4 — ANNOUNCED solo puede tener ATA futura

Para status `ANNOUNCED`, si `ATA` tiene valor y es **anterior** a la fecha actual, se reporta.

→ **Error** `INVALID_VALUE`

---

### Paso 5 — Combinación VesselStatus + OperationStatus

Cada combinación de status tiene un conjunto de operaciones válidas. Si la operación no corresponde al status, se reporta.

Tabla de combinaciones válidas:

| VesselStatus | OperationStatus válidos |
|---|---|
| ANNOUNCED | TO_DISCHARGE, TO_LOAD |
| AT_LOAD_PORT | TO_DISCHARGE, TO_LOAD, TO_REPAIR |
| DRIFTING | TO_REPAIR, TOWING |
| SAILED | LOADED, DISCHARGED |
| BERTHED | DISCHARGING, DISCHARGED, LOADING, LOADED, TO_REPAIR |
| ANCHORED | TO_DISCHARGE, TO_LOAD |

→ **Error** `INVALID_VALUE` en `OPERATION`

> **Dependencia:** Se excluyen filas donde `STATUS` o `OPERATION` tuvieron error de conversión (ambos deben ser válidos para poder comparar).

---

### Paso 6 — SAILED: exenciones y nulos en todas las columnas

Para buques con status `SAILED`, **todas las columnas deben tener valor**. Sin embargo, hay dos tipos de exención que relajan esta regla para `PRODUCT` y `MT_BY_PRODUCT`:

- **Por tipo de carga:** Si el `CargoType` es `STEEL`, `FERTILIZERS` o `PROJECT_CARGO`, se permiten esos campos vacíos y se rellenan automáticamente con valores por defecto.
- **Por empresa:** Si alguna de las columnas `SHIPOWNER`, `CHARTERER` o `AGENCY` contiene una empresa en la lista negra (blacklist), también aplica la exención.

Para las filas que no tienen exención (o para las columnas que no aplica la exención), cualquier campo nulo se reporta.

→ **Error** `MISSING_VALUE` por cada campo nulo

> **Dependencia:** Si una columna ya tiene un error registrado previamente en el reporte, **no se vuelve a reportar** como nulo aquí — se evita el doble reporte.

---

## 5. Validación de Intervalos de Fechas (`_cast_et_interval`)

Esta sección verifica que las fechas `ATA (ETA)`, `ETB` y `ETC` sean coherentes en orden cronológico, considerando también los periodos (`AM`/`PM`) como desempate.

> **Dependencia de entrada:** Depende del casteo correcto de las tres fechas y sus tres periodos. Si cualquiera de ellos tuvo error de conversión, la fila correspondiente se excluye del cálculo de ordinales para no generar falsos errores de orden.

### Regla 1 — Periodo presente pero fecha ausente

Si un periodo (AM/PM) tiene valor pero su fecha correspondiente está vacía (y la fecha no falló por error de conversión), se reporta.

→ **Error** `MISSING_VALUE` en el campo de periodo

---

### Regla 2 — ETB o ETC sin ETA

Si `ETB` o `ETC` tienen valor pero `ETA (ATA)` está vacía (y ATA no falló por error), se reporta.

→ **Error** `MISSING_VALUE` en ETB o ETC

> **Lógica:** ETA es prerequisito para poder definir ETB y ETC. Sin una fecha de llegada, no tiene sentido tener fechas de atraque o zarpe.

---

### Cálculo de ordinales

Para verificar el orden cronológico, cada fecha se convierte a un número ordinal multiplicado por 2, al que se le suma 1 si el periodo es `PM`. Esto permite comparar `AM/PM` sin ambigüedad. Las filas con cualquier error en los pasos anteriores de esta sección se excluyen de este cálculo.

---

## 6. Variante: `VariantLineUpProcessor`

Este procesador extiende el flujo base con una validación adicional sobre la columna `WINDOWS`.

**Qué hace:** Elimina espacios del valor y verifica que cumpla el formato `DD-DD` (dos números de dos dígitos separados por guión, ej: `12-34`).

**Si falla:** → **Error** con descripción del formato esperado

> **Dependencia:** Ninguna con otros pasos. Es una validación independiente que corre al final del proceso.
