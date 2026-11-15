# -*- coding: utf-8 -*-
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from asistente.chat import iniciar_chat
from asistente.recordatorios import GestorRecordatorios


class RagFalso:
    def __init__(self):
        self.preguntas = []

    def invoke(self, datos):
        self.preguntas.append(datos["input"])
        return {"answer": "respuesta del RAG"}


def _correr(entradas, rag=None, gestor=None, llm=None):
    rag = rag or RagFalso()
    gestor = gestor or GestorRecordatorios(MagicMock())
    if llm is None:
        llm = MagicMock()
        llm.invoke.return_value.content = '{"accion": "consulta"}'
    salida = io.StringIO()
    with patch("builtins.input", side_effect=entradas), redirect_stdout(salida):
        iniciar_chat(rag, gestor, llm)
    return salida.getvalue(), rag, gestor


class TestChat(unittest.TestCase):
    def test_salir(self):
        out, _, _ = _correr(["salir"])
        self.assertIn("Asistente iniciado", out)
        self.assertIn("No reemplaza la consulta con un profesional de la salud.", out)
        self.assertIn("¡Nos vemos!", out)

    def test_pregunta_va_al_rag(self):
        out, rag, _ = _correr(["¿Qué es la fibra?", "exit"])
        self.assertEqual(rag.preguntas, ["¿Qué es la fibra?"])
        self.assertIn("🤖 Asistente: respuesta del RAG", out)

    def test_mensaje_vacio_se_ignora(self):
        _, rag, _ = _correr(["", "   ", "salir"])
        self.assertEqual(rag.preguntas, [])

    def test_consulta_generica_va_al_rag(self):
        out, rag, _ = _correr(["Quiero reservar algo", "salir"])
        self.assertEqual(rag.preguntas, ["Quiero reservar algo"])
        self.assertIn("🤖 Asistente: respuesta del RAG", out)

    def test_prueban8n(self):
        llm = MagicMock()
        llm.invoke.return_value.content = '{"accion": "crear_tarea"}'
        with patch("asistente.chat.enviar_a_n8n_test") as prueba:
            out, rag, _ = _correr(["prueban8n", "salir"], llm=llm)
        prueba.assert_called_once_with({"accion": "crear_tarea"})
        self.assertEqual(rag.preguntas, [])
        self.assertIn("Ejecutando prueba de Tasks de n8n", out)

    def test_crea_tarea_con_el_historial_y_sigue_el_chat(self):
        resultado_tarea = {
            "accion": "crear_tarea",
            "titulo": "Comprar alimentos",
            "notas": "",
            "fecha_vencimiento": None,
        }
        historiales = []
        respuestas = iter([resultado_tarea, {"accion": "consulta"}])

        def detectar_fake(pregunta, llm, historial):
            historiales.append(list(historial))
            return next(respuestas)

        with patch(
            "asistente.chat.detectar_intencion_tarea",
            side_effect=detectar_fake,
        ), patch(
            "asistente.chat.enviar_a_n8n_test", return_value="Tarea creada."
        ) as enviar:
            out, rag, _ = _correr(
                ["creá una tarea para comprar alimentos", "¿Qué es la fibra?", "salir"]
            )

        enviar.assert_called_once_with(resultado_tarea)
        self.assertEqual(
            historiales,
            [[], [{
                "usuario": "creá una tarea para comprar alimentos",
                "asistente": "Tarea creada.",
            }]],
        )
        self.assertEqual(rag.preguntas, ["¿Qué es la fibra?"])
        self.assertIn("Creando tarea en Google Tasks", out)

    def test_turno_se_envia_como_accion_a_n8n(self):
        with patch(
            "asistente.chat.llamar_n8n",
            return_value={"success": True, "mensaje": "recibido"},
        ) as n8n:
            out, rag, _ = _correr(["Quiero agendar un turno", "salir"])

        n8n.assert_called_once_with(
            "agendar_turno", {"mensaje": "Quiero agendar un turno"}
        )
        self.assertEqual(rag.preguntas, [])
        self.assertIn("recibido", out)

    def test_recordatorio_tiene_prioridad_y_mantiene_conversacion(self):
        gestor = MagicMock()
        gestor.hay_pendiente.side_effect = [False, True]
        gestor.responder.side_effect = ["¿qué día?", "listo"]
        out, rag, _ = _correr(["recordame tomar agua", "mañana", "salir"], gestor=gestor)
        self.assertEqual(rag.preguntas, [])
        self.assertEqual(gestor.responder.call_count, 2)
        self.assertIn("🤖 Asistente: ¿qué día?", out)

    def test_error_del_rag_no_corta_el_chat(self):
        rag = MagicMock()
        rag.invoke.side_effect = [RuntimeError("falló Groq"), {"answer": "ok"}]
        out, _, _ = _correr(["pregunta 1", "pregunta 2", "salir"], rag=rag)
        self.assertIn("⚠️ Ocurrió un error al consultar el asistente: falló Groq", out)
        self.assertIn("🤖 Asistente: ok", out)

    def test_ctrl_c_sale_limpio(self):
        out, _, _ = _correr([KeyboardInterrupt()])
        self.assertIn("¡Nos vemos!", out)


if __name__ == "__main__":
    unittest.main()
