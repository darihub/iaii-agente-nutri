# Contrato del webhook de n8n

El asistente envía `POST` con cuerpo JSON a `N8N_WEBHOOK_URL`. El workflow de n8n debe
enrutar según el campo `accion` (nodo *Switch*). Estos son los tipos de mensaje
que envía el código actual.

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
El contenido es fijo:

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

## Sobre el campo `origen`

Vale `"Colab_IA2"` por herencia del notebook. Se conserva tal cual porque el workflow de
n8n podría filtrar por ese valor. Si querés cambiarlo, modificá `N8N_ORIGEN` en
`asistente/config.py` **y** el workflow.
