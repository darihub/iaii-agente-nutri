# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

import requests

from asistente import config, n8n_client


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




if __name__ == "__main__":
    unittest.main()
