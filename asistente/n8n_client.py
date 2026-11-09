# -*- coding: utf-8 -*-
"""FASE 3: Acción y automatización. Conexión con n8n mediante webhooks.

Reúne las tres funciones de envío que tenía el notebook:

- enviar_a_n8n:       solicitud de turno (payload {"mensaje", "origen"}).
- enviar_a_n8n_test:  prueba fija de Google Tasks (acción "crear_tarea").
- llamar_n8n:         envío genérico con el campo "accion" (lo usan los recordatorios).

La URL se lee de `config.N8N_WEBHOOK_URL` en cada llamada.
"""
import requests

from . import config

_PLACEHOLDER_URL = "PEGAR_AQUI_LA_URL_DEL_WEBHOOK"


def _webhook_sin_configurar():
    return not config.N8N_WEBHOOK_URL or config.N8N_WEBHOOK_URL == _PLACEHOLDER_URL


def enviar_a_n8n(mensaje_usuario, timeout=30):
    if _webhook_sin_configurar():
        return "⚠️ Configurá N8N_WEBHOOK_URL antes de enviar solicitudes."

    payload = {"mensaje": mensaje_usuario, "origen": config.N8N_ORIGEN}
    try:
        respuesta = requests.post(config.N8N_WEBHOOK_URL, json=payload, timeout=timeout)
        respuesta.raise_for_status()

        try:
            return respuesta.json()
        except ValueError:
            return "✅ Solicitud enviada a n8n con éxito."

    except requests.exceptions.Timeout:
        return f"n8n no respondió en {timeout} segundos."
    except requests.exceptions.ConnectionError:
        return "⚠️ No se pudo conectar con n8n. Revisá la URL del webhook."
    except requests.exceptions.HTTPError as e:
        if e.response is None:
            return f"⚠️ Error en n8n: {e}"
        return f"⚠️ Error en n8n: {e.response.status_code} - {e.response.text[:200]}"
    except requests.exceptions.RequestException as e:
        return f"⚠️ Error de conexión: {e}"


def enviar_a_n8n_test(mensaje_usuario, timeout=30):
    if _webhook_sin_configurar():
        return "⚠️ Configurá N8N_WEBHOOK_URL antes de enviar solicitudes."

    test_json = {
        "accion": "crear_tarea",
        "titulo": "Prueba de Google Tasks",
        "notas": "Tarea creada desde el chatbot",
        "fecha_vencimiento": "2026-11-10T00:00:00.000Z",
    }

    respuesta = requests.post(config.N8N_WEBHOOK_URL, json=test_json, timeout=timeout)

    resultado = respuesta.json()

    if resultado.get("success"):
        print("Sistema:", resultado["mensaje"])
    else:
        print("Error:", resultado["mensaje"])


def llamar_n8n(accion, datos, timeout=30):
    """Envío genérico a n8n: el campo 'accion' lo enruta el nodo Switch.
    Sirve para recordatorios y para futuras acciones (tareas, recetas)."""
    if _webhook_sin_configurar():
        return {"success": False, "mensaje": "Configurá N8N_WEBHOOK_URL antes de enviar solicitudes."}
    payload = {"accion": accion, "origen": config.N8N_ORIGEN, **datos}
    try:
        r = requests.post(config.N8N_WEBHOOK_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        try:
            resultado = r.json()
            if isinstance(resultado, list) and resultado:
                resultado = resultado[0]
            return resultado if isinstance(resultado, dict) else {"success": True, "mensaje": str(resultado)}
        except ValueError:
            return {"success": True, "mensaje": "Solicitud enviada a n8n."}
    except requests.exceptions.Timeout:
        return {"success": False, "mensaje": f"n8n no respondió en {timeout} segundos."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "mensaje": "No se pudo conectar con n8n. Revisá la URL del webhook."}
    except requests.exceptions.HTTPError as e:
        if e.response is None:
            return {"success": False, "mensaje": f"Error en n8n: {e}"}
        return {"success": False, "mensaje": f"Error en n8n: {e.response.status_code} - {e.response.text[:200]}"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "mensaje": f"Error de conexión: {e}"}
