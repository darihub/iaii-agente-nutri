# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from asistente import config
from asistente.recordatorios import GestorRecordatorios, detectar_intencion_recordatorio


class _Respuesta:
    def __init__(self, content):
        self.content = content


class LLMFalso:
    """Devuelve, en orden, las respuestas JSON que se le indiquen."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)

    def invoke(self, mensajes):
        return _Respuesta(self.respuestas.pop(0))


class TestDeteccion(unittest.TestCase):
    def test_detecta_pedidos_de_recordatorio(self):
        for frase in ["Recordame tomar agua", "recuérdame llamar", "avisame mañana",
                      "mandame un correo el viernes", "quiero un recordatorio"]:
            self.assertTrue(detectar_intencion_recordatorio(frase), frase)

    def test_no_detecta_preguntas_comunes(self):
        for frase in ["¿Qué es la fibra?", "quiero un turno", "hola"]:
            self.assertFalse(detectar_intencion_recordatorio(frase), frase)


class TestGestorRecordatorios(unittest.TestCase):
    def test_conserva_datos_entre_turnos_y_envia_a_n8n(self):
        llm = LLMFalso(
            '{"fecha": "2999-01-01", "hora": "10:30", "mensaje": null, "repeticiones": null, "intervalo_dias": null}',
            '{"fecha": null, "hora": null, "mensaje": "tomar agua", "repeticiones": 3, "intervalo_dias": 2}',
        )
        gestor = GestorRecordatorios(llm)

        r1 = gestor.responder("recordame algo el 1 de enero de 2999 a las 10:30")
        self.assertIn("necesito unos datos más", r1)
        self.assertIn("qué querés que te recuerde", r1)
        self.assertIn("cuántas veces", r1)
        self.assertTrue(gestor.hay_pendiente())

        with patch("asistente.recordatorios.llamar_n8n",
                   return_value={"success": True, "mensaje": "ok"}) as n8n, \
                patch.object(config, "EMAIL_DESTINO", ""):
            r2 = gestor.responder("tomar agua, 3 veces cada 2 días")

        n8n.assert_called_once_with("enviar_recordatorio", {
            "fecha": "2999-01-01T10:30:00-03:00",
            "mensaje": "tomar agua",
            "repeticiones": 3,
            "intervalo_dias": 2,
            "email": "",
        })
        self.assertIn("✅ Recordatorio programado", r2)
        self.assertIn("3 veces, una cada 2 día(s), desde el 01/01/2999 a las 10:30", r2)
        self.assertFalse(gestor.hay_pendiente())

    def test_una_sola_repeticion_y_hora_por_defecto(self):
        llm = LLMFalso(
            '{"fecha": "2999-05-20", "hora": null, "mensaje": "ir al nutricionista",'
            ' "repeticiones": 1, "intervalo_dias": null}'
        )
        gestor = GestorRecordatorios(llm)
        with patch("asistente.recordatorios.llamar_n8n",
                   return_value={"success": True}) as n8n:
            r = gestor.responder("avisame que tengo nutricionista")
        datos = n8n.call_args[0][1]
        self.assertEqual(datos["fecha"], "2999-05-20T09:00:00-03:00")
        self.assertEqual(datos["intervalo_dias"], 1)
        self.assertIn("te lo envío por correo el 20/05/2999 a las 09:00.", r)

    def test_repeticiones_se_limitan_a_30(self):
        llm = LLMFalso(
            '{"fecha": "2999-01-01", "mensaje": "x", "repeticiones": 99, "intervalo_dias": null}'
        )
        gestor = GestorRecordatorios(llm)
        with patch("asistente.recordatorios.llamar_n8n",
                   return_value={"success": True}) as n8n:
            gestor.responder("recordame x")
        self.assertEqual(n8n.call_args[0][1]["repeticiones"], 30)

    def test_fecha_pasada_se_vuelve_a_preguntar(self):
        llm = LLMFalso(
            '{"fecha": "2000-01-01", "mensaje": "x", "repeticiones": 1, "intervalo_dias": null}'
        )
        gestor = GestorRecordatorios(llm)
        r = gestor.responder("recordame x el 1/1/2000")
        self.assertIn("Esa fecha ya pasó", r)
        self.assertNotIn("fecha", gestor.pendiente)
        self.assertEqual(gestor.pendiente["mensaje"], "x")  # lo ya informado se conserva

    def test_cancelar_borra_el_pedido_en_curso(self):
        llm = LLMFalso('{"fecha": null, "mensaje": "x", "repeticiones": null, "intervalo_dias": null}')
        gestor = GestorRecordatorios(llm)
        gestor.responder("recordame x")
        self.assertTrue(gestor.hay_pendiente())
        self.assertIn("cancelé el recordatorio", gestor.responder("cancelar"))
        self.assertFalse(gestor.hay_pendiente())

    def test_cancelar_sin_pedido_en_curso_no_cancela_nada(self):
        llm = LLMFalso('{"fecha": null, "mensaje": null, "repeticiones": null, "intervalo_dias": null}')
        gestor = GestorRecordatorios(llm)
        r = gestor.responder("recordame cancelar la suscripción")
        self.assertNotIn("cancelé", r)

    def test_error_de_n8n_se_informa_al_usuario(self):
        llm = LLMFalso(
            '{"fecha": "2999-01-01", "mensaje": "x", "repeticiones": 1, "intervalo_dias": null}'
        )
        gestor = GestorRecordatorios(llm)
        with patch("asistente.recordatorios.llamar_n8n",
                   return_value={"success": False, "mensaje": "n8n no respondió en 30 segundos."}):
            r = gestor.responder("recordame x")
        self.assertEqual(r, "⚠️ No pude programar el recordatorio: n8n no respondió en 30 segundos.")

    def test_respuesta_del_llm_invalida_no_rompe(self):
        gestor = GestorRecordatorios(LLMFalso("no es json"))
        r = gestor.responder("recordame algo")
        self.assertIn("necesito unos datos más", r)


if __name__ == "__main__":
    unittest.main()
