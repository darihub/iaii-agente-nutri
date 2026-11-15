# n8n: un Google Sheet por usuario (rama `crear_receta`)

Guía para armar la rama de recetas en n8n. El programa manda `usuario`, `email` y `recetas`
(ver [`contrato_n8n.md`](contrato_n8n.md), sección 4). n8n tiene que:

1. buscar si ese usuario ya tiene un Excel;
2. si no lo tiene, crearlo copiando una plantilla y anotarlo en un índice;
3. agregar una fila por receta en **ese** Excel;
4. responder con el link.

## Qué crear antes (una sola vez, en Google Drive)

| Archivo | Contenido | Para qué |
|---|---|---|
| **Plantilla Recetas** | Hoja `Hoja 1` con los encabezados en la fila 1: `Nombre`, `Ingredientes`, `Calorías`, `Proteínas`, `Preparación` | Se copia para cada usuario nuevo. |
| **Recetas - Usuarios** | Hoja `Hoja 1` con los encabezados: `usuario`, `id_sheet`, `url` | Índice: qué Excel es de quién. |

Credenciales en n8n: la de **Google Sheets** (ya la tenés) y una nueva de **Google Drive**
(*Create new credential → Sign in with Google*).

## Nodos de la rama

```
Switch (crear_receta)
  → Buscar usuario → ¿Ya tiene Excel?
        ├─ NO → Copiar plantilla → Guardar en índice ─┐
        └─ SÍ ────────────────────────────────────────┤
                                                      ▼
                                              Preparar filas → Guardar Recetas en Sheet
                                                      → Juntar Resultados → Respond to Webhook (Recetas)
```

Borrá los nodos viejos de esta rama (`Separar Recetas (Split Out)` y `Eligue el Excel`):
el nodo *Preparar filas* hace el trabajo de separar las recetas.

### 1. Buscar usuario
- Nodo **Google Sheets** → operación **Get row(s) in sheet**.
- Document: *Recetas - Usuarios*. Sheet: `Hoja 1`.
- Filters: columna `usuario` = `{{ $('Webhook').item.json.body.usuario }}`.
- En la pestaña **Settings** del nodo activá **Always Output Data**. Si no lo hacés, cuando el
  usuario es nuevo no hay resultados y el flujo se corta ahí.

### 2. ¿Ya tiene Excel?
- Nodo **IF**. Condición: `{{ $json.id_sheet }}` → *String* → **is not empty**.
- Salida **true**: el usuario ya tiene archivo. Salida **false**: hay que crearlo.

### 3. Copiar plantilla (salida false)
- Nodo **Google Drive** → *File* → **Copy**.
- File: *By ID* con el ID de *Plantilla Recetas* (es el texto largo del link, entre `/d/` y `/edit`).
- Name: `Recetas - {{ $('Webhook').item.json.body.usuario }}`.

### 4. Guardar en índice (a continuación de Copiar plantilla)
- Nodo **Google Sheets** → **Append row**. Document: *Recetas - Usuarios*.
- `usuario` = `{{ $('Webhook').item.json.body.usuario }}`
- `id_sheet` = `{{ $('Copiar plantilla').item.json.id }}`
- `url` = `https://docs.google.com/spreadsheets/d/{{ $('Copiar plantilla').item.json.id }}/edit`

*(Opcional)* **Compartir el archivo**: después de *Copiar plantilla* agregá un nodo **Google Drive →
File → Share** con File ID `{{ $('Copiar plantilla').item.json.id }}`, Role *Reader*, Type *User* y
Email `{{ $('Webhook').item.json.body.email }}`. Ponele un **IF** antes para que solo corra cuando
`email` no está vacío.

### 5. Preparar filas
Las dos ramas (la que creó el archivo y la que ya lo tenía) se conectan a este nodo.
- Nodo **Code** → *Run Once for All Items* → JavaScript:

```javascript
const body = $('Webhook').first().json.body;
const buscado = $('Buscar usuario').first().json;

// Usuario existente: el ID viene del índice. Usuario nuevo: de la copia recién creada.
let id = buscado.id_sheet;
if (!id) id = $('Copiar plantilla').first().json.id;

return body.recetas.map(r => ({ json: { ...r, id_sheet: id } }));
```

Devuelve un item por receta, cada uno con el ID de su Excel.

### 6. Guardar Recetas en Sheet (Append Row)
Es el nodo que ya tenés, con **un solo cambio**: el documento ahora se elige por ID.
- Document: cambiá *From list* por **By ID** y poné `{{ $json.id_sheet }}`.
- Sheet: *By Name* → `Hoja 1`.
- Las columnas quedan igual (`{{ $json.nombre }}`, `{{ $json.ingredientes }}`, etc.).

### 7. Juntar Resultados (Aggregate)
Sin cambios. Hace que el Respond corra una sola vez.

### 8. Respond to Webhook (Recetas)
- Respond With: **JSON**. Response Body:

```json
{
  "success": true,
  "mensaje": "Recetas cargadas en tu Excel",
  "url": "https://docs.google.com/spreadsheets/d/{{ $('Preparar filas').first().json.id_sheet }}/edit"
}
```

## Cómo probarlo

1. Con el workflow **activado** y la URL de producción en el `.env`, corré `python main.py`.
   La primera vez pide un alias (se guarda en `.usuario`).
2. Pedí `armame 2 recetas altas en proteína`.
3. Tiene que imprimir `✅ ...` y un link a **Tu Excel**. En Drive aparece `Recetas - <alias>`, y en
   *Recetas - Usuarios* una fila nueva.
4. Pedí recetas otra vez: tiene que **reutilizar** el mismo archivo y agregar filas debajo,
   sin crear uno nuevo.
5. Probá con otro alias (borrá `.usuario` o cambiá `USUARIO` en el `.env`): tiene que crear
   un archivo distinto.

## Problemas frecuentes

| Síntoma | Causa |
|---|---|
| Se corta en *Buscar usuario* con usuario nuevo | Falta **Always Output Data** en Settings. |
| Crea un archivo nuevo en cada pedido | El filtro de *Buscar usuario* no coincide (revisá el nombre de la columna `usuario`) o *Guardar en índice* no llegó a escribir. |
| `The resource you are requesting could not be found` en Append Row | El ID no es válido: revisá que *Preparar filas* devuelva `id_sheet` y que el documento esté en modo *By ID*. |
| El programa muestra `✅ Solicitud enviada a n8n.` sin link | El nodo Respond no devolvió JSON: revisá el *Response Body* del paso 8. |
| Error de permisos al copiar | La cuenta de Google conectada no tiene acceso a *Plantilla Recetas*. |

## Privacidad

- Los archivos se crean en el Drive de la cuenta de Google conectada a n8n. Quien administra esa
  cuenta puede abrirlos todos.
- Por eso el programa pide un **alias** y no datos personales (ver `docs/limites_seguridad.md`).
- Compartir con *Reader* por correo es más privado que un link abierto a cualquiera.
