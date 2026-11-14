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


def _correr(entradas, rag=None, gestor=None, intencion_tarea=None):
    rag = rag or RagFalso()
    gestor = gestor or GestorRecordatorios(MagicMock())
    salida = io.StringIO()
    intencion_tarea = intencion_tarea or {"accion": "consulta"}
    with patch("builtins.input", side_effect=entradas), \
         patch("asistente.chat.detectar_intencion_tarea", return_value=intencion_tarea), \
         redirect_stdout(salida):
        iniciar_chat(rag, gestor, MagicMock())
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

    def test_crear_tarea_se_envia_a_n8n(self):
        tarea = {"accion": "crear_tarea", "titulo": "Prueba"}
        with patch("asistente.chat.enviar_a_n8n_test") as prueba:
            out, rag, _ = _correr(["crear tarea", "salir"], intencion_tarea=tarea)
        prueba.assert_called_once_with(tarea)
        self.assertEqual(rag.preguntas, [])
        self.assertIn("Ejecutando prueba de Tasks de n8n", out)

    def test_recordatorio_tiene_prioridad_y_mantiene_conversacion(self):
        gestor = MagicMock()
        gestor.hay_pendiente.side_effect = [False, True]
        gestor.responder.side_effect = ["¿qué día?", "listo"]
        out, rag, _ = _correr(["recordame", "mañana", "salir"], gestor=gestor)
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
