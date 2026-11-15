# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

import requests
import json

from asistente import config, n8n_client
from asistente.tareas import detectar_intencion_tarea



def _resp(json_data=None, json_error=False, status=200, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    if json_error:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_data
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(response=r)
    return r


class TestLlamarN8n(unittest.TestCase):
    def setUp(self):
        p = patch.object(config, "N8N_WEBHOOK_URL", "https://n8n.test/webhook/x")
        p.start()
        self.addCleanup(p.stop)

    def test_payload_incluye_accion_origen_y_datos(self):
        with patch("asistente.n8n_client.requests.post",
                   return_value=_resp({"success": True, "mensaje": "ok"})) as post:
            r = n8n_client.llamar_n8n("enviar_recordatorio", {"mensaje": "hola"})
        post.assert_called_once_with(
            "https://n8n.test/webhook/x",
            json={"accion": "enviar_recordatorio", "origen": "Colab_IA2", "mensaje": "hola"},
            timeout=30,
        )
        self.assertEqual(r, {"success": True, "mensaje": "ok"})

    def test_respuesta_lista_toma_el_primer_elemento(self):
        with patch("asistente.n8n_client.requests.post",
                   return_value=_resp([{"success": True, "mensaje": "uno"}, {"x": 1}])):
            self.assertEqual(n8n_client.llamar_n8n("a", {})["mensaje"], "uno")

    def test_respuesta_no_json(self):
        with patch("asistente.n8n_client.requests.post", return_value=_resp(json_error=True)):
            self.assertEqual(n8n_client.llamar_n8n("a", {}),
                             {"success": True, "mensaje": "Solicitud enviada a n8n."})

    def test_errores(self):
        casos = [
            (requests.exceptions.Timeout(), "n8n no respondió en 30 segundos."),
            (requests.exceptions.ConnectionError(), "No se pudo conectar con n8n. Revisá la URL del webhook."),
        ]
        for excepcion, esperado in casos:
            with patch("asistente.n8n_client.requests.post", side_effect=excepcion):
                r = n8n_client.llamar_n8n("a", {})
            self.assertFalse(r["success"])
            self.assertEqual(r["mensaje"], esperado)

    def test_error_http(self):
        with patch("asistente.n8n_client.requests.post",
                   return_value=_resp(status=404, text="not found")):
            r = n8n_client.llamar_n8n("a", {})
        self.assertEqual(r, {"success": False, "mensaje": "Error en n8n: 404 - not found"})

    def test_sin_url_configurada(self):
        with patch.object(config, "N8N_WEBHOOK_URL", "PEGAR_AQUI_LA_URL_DEL_WEBHOOK"):
            self.assertFalse(n8n_client.llamar_n8n("a", {})["success"])



class TestEnviarAN8nTest(unittest.TestCase):
    def setUp(self):
        p = patch.object(
            config,
            "N8N_WEBHOOK_URL",
            "https://n8n.test/webhook-test/x"
        )
        p.start()
        self.addCleanup(p.stop)

        # Simula una tarea que el LLM construyó
        # utilizando el historial de conversación.
        self.tarea_receta = {
            "accion": "crear_tarea",
            "titulo": "Receta de panqueques saludables",
            "notas": (
                "Ingredientes: 2 huevos, 1 banana y avena.\n"
                "Preparación: mezclar los ingredientes "
                "y cocinar en una sartén."
            ),
            "fecha_vencimiento": None
        }

    def test_envia_receta_completa_del_historial(self):
        with patch(
            "asistente.n8n_client.requests.post",
            return_value=_resp({
                "success": True,
                "mensaje": "Tarea creada."
            })
        ) as post:

            resultado = n8n_client.enviar_a_n8n_task(
                self.tarea_receta
            )

        post.assert_called_once_with(
            "https://n8n.test/webhook-test/x",
            json=self.tarea_receta,
            timeout=30
        )

        self.assertEqual(resultado, "Tarea creada.")

        # Verifica que no se envió solamente "receta".
        payload = post.call_args.kwargs["json"]
        self.assertIn("2 huevos", payload["notas"])
        self.assertIn("cocinar", payload["notas"])

    def test_retorna_el_mensaje_de_respuesta(self):
        with patch(
            "asistente.n8n_client.requests.post",
            return_value=_resp({
                "success": True,
                "mensaje": "Tarea creada."
            })
        ):
            resultado = n8n_client.enviar_a_n8n_task(
                self.tarea_receta
            )

        self.assertEqual(resultado, "Tarea creada.")

    def test_respuesta_sin_mensaje(self):
        with patch(
            "asistente.n8n_client.requests.post",
            return_value=_resp({"success": True})
        ):
            resultado = n8n_client.enviar_a_n8n_task(
                self.tarea_receta
            )

        self.assertEqual(
            resultado,
            "La solicitud fue procesada."
        )

    def test_error_http(self):
        with patch(
            "asistente.n8n_client.requests.post",
            return_value=_resp(
                status=500,
                text="Falló el nodo de Google Tasks"
            )
        ):
            resultado = n8n_client.enviar_a_n8n_task(
                self.tarea_receta
            )

        self.assertEqual(
            resultado,
            "Error HTTP 500 de n8n: "
            "Falló el nodo de Google Tasks"
        )

    def test_timeout(self):
        with patch(
            "asistente.n8n_client.requests.post",
            side_effect=requests.exceptions.Timeout()
        ):
            resultado = n8n_client.enviar_a_n8n_task(
                self.tarea_receta
            )

        self.assertEqual(
            resultado,
            "n8n no respondió en 30 segundos."
        )



class TestMemoriaTareas(unittest.TestCase):

    def test_recupera_receta_del_historial(self):
        historial = [
            {
                "usuario": "Dame una receta de panqueques",
                "asistente": (
                    "Ingredientes: 2 huevos, 1 banana y avena. "
                    "Preparación: mezclar todo y cocinar."
                )
            }
        ]

        llm = MagicMock()
        llm.invoke.return_value.content = json.dumps({
            "accion": "crear_tarea",
            "titulo": "Panqueques",
            "notas": (
                "Ingredientes: 2 huevos, 1 banana y avena. "
                "Preparación: mezclar todo y cocinar."
            ),
            "fecha_vencimiento": None
        })

        resultado = detectar_intencion_tarea(
            "Guardá esa receta en Google Tasks",
            llm,
            historial
        )

        self.assertEqual(resultado["accion"], "crear_tarea")
        self.assertIn("2 huevos", resultado["notas"])

        # Comprueba que el historial llegó al LLM.
        mensajes = llm.invoke.call_args.args[0]
        self.assertIn(
            "2 huevos",
            mensajes[1].content
        )


if __name__ == "__main__":
    unittest.main()
