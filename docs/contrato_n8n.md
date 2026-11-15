# Contrato del webhook de n8n

El asistente envía `POST` con cuerpo JSON a `N8N_WEBHOOK_URL`. El workflow de n8n debe
enrutar según el campo `accion` (nodo *Switch*). El código envía recordatorios,
tareas y recetas.

## 1. Recordatorio por correo

Se envía cuando el usuario completó fecha, mensaje y repeticiones
(`n8n_client.llamar_n8n`, acción `enviar_recordatorio`).

```json
{
  "accion": "enviar_recordatorio",
  "origen": "Colab_IA2",
  "fecha": "2026-11-10T08:00:00-03:00",
  "mensaje": "tomar agua",
  "repeticiones": 3,
  "intervalo_dias": 2,
  "email": ""
}
```

| Campo | Descripción |
|---|---|
| `fecha` | Primer envío, ISO 8601 con zona horaria de Argentina (UTC-03:00). |
| `mensaje` | Texto a recordar. |
| `repeticiones` | Cantidad total de envíos (1 a 30). |
| `intervalo_dias` | Días entre envíos (mínimo 1). |
| `email` | Destinatario. Vacío = usar el correo por defecto del nodo Gmail. |

**Respuesta esperada** (objeto, o lista cuyo primer elemento es el objeto):

```json
{ "success": true, "mensaje": "Recordatorio programado." }
```

Si `success` no es verdadero, el bot informa `⚠️ No pude programar el recordatorio: <mensaje>`.

> Los recordatorios quedan esperando en el nodo *Wait* de n8n: el workflow debe estar
> **activado** y usarse la URL de **producción** (`/webhook/...`).

## 2. Prueba de Google Tasks

Se envía cuando el usuario escribe `prueban8n` (`n8n_client.enviar_a_n8n_test`).
Para una tarea detectada por el LLM se envían los campos extraídos (`titulo`,
`notas` y `fecha_vencimiento`) con `accion: "crear_tarea"`. El comando de prueba
usa este contenido fijo:

```json
{
  "accion": "crear_tarea",
  "titulo": "Prueba de Google Tasks",
  "notas": "Tarea creada desde el chatbot",
  "fecha_vencimiento": "2026-11-10T00:00:00.000Z"
}
```

Debe responder `{"success": true/false, "mensaje": "..."}`; el bot imprime
`Sistema: <mensaje>` o `Error: <mensaje>`.

## 3. Recetas en un Google Sheet por usuario

Se envía cuando el usuario pide recetas (por ejemplo: *"armame 3 recetas altas en proteína"*;
`recetas.GeneradorRecetas`, acción `crear_receta`). Las recetas salen de los PDF (RAG) y
las calorías/proteínas quedan vacías si no figuran en ellos. Cada usuario tiene **su propio**
Google Sheet: n8n lo busca por el campo `usuario` y, si no existe, lo crea.

```json
{
  "accion": "crear_receta",
  "origen": "Colab_IA2",
  "usuario": "nito",
  "email": "",
  "recetas": [
    {
      "nombre": "Tortilla de espinaca",
      "ingredientes": "huevos, espinaca, cebolla",
      "calorias": "",
      "proteinas": "",
      "preparacion": "Saltear la verdura, sumar el huevo batido y cocinar."
    }
  ]
}
```

| Campo | Descripción |
|---|---|
| `usuario` | Identificador del usuario: alias o correo, en minúsculas (`config.obtener_usuario`). Es la clave para encontrar su Excel. |
| `email` | Correo del usuario si se conoce (el propio `usuario` si es un correo, o `EMAIL_DESTINO`). Vacío si no hay. n8n puede usarlo para compartirle el archivo. |
| `recetas` | Entre 1 y 3 recetas con los campos `nombre`, `ingredientes`, `calorias`, `proteinas`, `preparacion` (todos texto). |

**Respuesta esperada:**

```json
{
  "success": true,
  "mensaje": "Recetas cargadas en tu Excel",
  "url": "https://docs.google.com/spreadsheets/d/<ID>/edit"
}
```

`url` es opcional: si viene, el bot la muestra. Si `success` no es verdadero, el bot informa
`⚠️ No pude cargar las recetas en el Sheet: <mensaje>`.

La rama de n8n (índice de usuarios, copia de una plantilla, carga de filas) está explicada paso
a paso en [`n8n_recetas_por_usuario.md`](n8n_recetas_por_usuario.md).

## Sobre el campo `origen`

Vale `"Colab_IA2"` por herencia del notebook. Se conserva tal cual porque el workflow de
n8n podría filtrar por ese valor. Si querés cambiarlo, modificá `N8N_ORIGEN` en
`asistente/config.py` **y** el workflow.
