# -*- coding: utf-8 -*-
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from asistente import config
from asistente.chat import iniciar_chat
from asistente.recetas import (
    GeneradorRecetas,
    SinRecetas,
    _normalizar,
    _parsear_recetas,
    detectar_intencion_recetas,
)
from asistente.recordatorios import GestorRecordatorios

JSON_OK = (
    '{"recetas":[{"nombre":"Tortilla","ingredientes":"huevos","calorias":"",'
    '"proteinas":"","preparacion":"Cocinar."}]}'
)
JSON_VACIO = '{"recetas":[]}'


def _generador(texto_llm, usuario="nito"):
    """GeneradorRecetas sin LangChain: la cadena se reemplaza por un falso."""
    g = GeneradorRecetas.__new__(GeneradorRecetas)
    g.usuario = usuario
    g.chain = MagicMock()
    g.chain.invoke.return_value = {"answer": texto_llm}
    return g


class TestDeteccion(unittest.TestCase):
    def test_pedidos_de_recetas(self):
        for texto in [
            "armame 3 recetas altas en proteína",
            "pasá las recetas al excel",
            "quiero una receta",
            "haceme una receta para cuidarme",
        ]:
            self.assertTrue(detectar_intencion_recetas(texto), texto)

    def test_consultas_normales_no_disparan(self):
        for texto in ["¿Qué es la fibra dietaria?", "¿Qué dice el libro sobre las recetas?"]:
            self.assertFalse(detectar_intencion_recetas(texto), texto)


class TestParseo(unittest.TestCase):
    def test_json_valido(self):
        self.assertEqual(len(_parsear_recetas(JSON_OK)), 1)

    def test_json_con_texto_alrededor(self):
        self.assertEqual(len(_parsear_recetas("Acá va:\n" + JSON_OK + "\nlisto")), 1)

    def test_sin_json(self):
        self.assertIsNone(_parsear_recetas("no sé"))

    def test_lista_vacia_no_es_error_de_parseo(self):
        self.assertEqual(_parsear_recetas(JSON_VACIO), [])

    def test_json_roto_se_repara_si_esta_json_repair(self):
        roto = '{"recetas":[{"nombre":"Ensalada","ingredientes":"lechuga","preparacion":"Mezclar"}'
        try:
            import json_repair  # noqa: F401
        except ImportError:
            self.skipTest("json-repair no instalado")
        self.assertEqual(_parsear_recetas(roto)[0]["nombre"], "Ensalada")

    def test_normalizar_completa_campos_y_limita(self):
        filas = _normalizar([{"nombre": "A", "calorias": 250}] + [{"nombre": str(i)} for i in range(10)] + [{"x": 1}])
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[0]["calorias"], "250")
        self.assertEqual(filas[0]["proteinas"], "")


class TestGenerador(unittest.TestCase):
    def test_generar_ok(self):
        self.assertEqual(_generador(JSON_OK).generar("recetas")[0]["nombre"], "Tortilla")

    def test_la_consulta_al_rag_refuerza_el_pedido(self):
        g = _generador(JSON_OK)
        g.generar("para cuidarme")
        consulta = g.chain.invoke.call_args.args[0]["input"]
        self.assertIn("para cuidarme", consulta)
        self.assertIn("ingredientes", consulta)

    def test_json_invalido_reintenta_y_falla(self):
        g = _generador("basura sin json")
        with self.assertRaises(ValueError) as ctx:
            g.generar("recetas", intentos=2)
        self.assertNotIsInstance(ctx.exception, SinRecetas)
        self.assertEqual(g.chain.invoke.call_count, 2)

    def test_lista_vacia_lanza_sin_recetas(self):
        with self.assertRaises(SinRecetas):
            _generador(JSON_VACIO).generar("para cuidarme", intentos=2)

    def test_responder_envia_usuario_y_recetas_a_n8n(self):
        g = _generador(JSON_OK, usuario="nito")
        resp = {"success": True, "mensaje": "Recetas cargadas en tu Excel", "url": "https://docs.google.com/x"}
        with patch("asistente.recetas.llamar_n8n", return_value=resp) as n8n:
            texto = g.responder("armame recetas")
        accion, datos = n8n.call_args.args[:2]
        self.assertEqual(accion, "crear_receta")
        self.assertEqual(datos["usuario"], "nito")
        self.assertEqual(datos["recetas"][0]["nombre"], "Tortilla")
        self.assertIn("✅", texto)
        self.assertIn("Tortilla", texto)
        self.assertIn("https://docs.google.com/x", texto)

    def test_responder_sin_url_no_muestra_link(self):
        g = _generador(JSON_OK)
        with patch("asistente.recetas.llamar_n8n", return_value={"success": True, "mensaje": "ok"}):
            self.assertNotIn("Tu Excel", g.responder("armame recetas"))

    def test_usuario_con_mail_se_manda_como_email(self):
        g = _generador(JSON_OK, usuario="ana@mail.com")
        with patch("asistente.recetas.llamar_n8n", return_value={"success": True}) as n8n:
            g.responder("armame recetas")
        self.assertEqual(n8n.call_args.args[1]["email"], "ana@mail.com")

    def test_usuario_alias_usa_email_destino_si_existe(self):
        g = _generador(JSON_OK, usuario="nito")
        with patch.object(config, "EMAIL_DESTINO", "dest@mail.com"), \
                patch("asistente.recetas.llamar_n8n", return_value={"success": True}) as n8n:
            g.responder("armame recetas")
        self.assertEqual(n8n.call_args.args[1]["email"], "dest@mail.com")

    def test_responder_error_de_n8n(self):
        g = _generador(JSON_OK)
        with patch("asistente.recetas.llamar_n8n", return_value={"success": False, "mensaje": "n8n no respondió"}):
            self.assertIn("n8n no respondió", g.responder("armame recetas"))

    def test_responder_json_invalido(self):
        self.assertIn("No pude generar las recetas", _generador("nada").responder("armame recetas"))

    def test_responder_sin_recetas_da_mensaje_util(self):
        texto = _generador(JSON_VACIO).responder("haceme una receta para cuidarme")
        self.assertIn("No encontré recetas", texto)
        self.assertIn("más concreto", texto)


class TestChatRecetas(unittest.TestCase):
    def test_pedido_de_recetas_va_al_generador_y_no_al_rag(self):
        rag = MagicMock()
        llm = MagicMock()
        generador = MagicMock()
        generador.responder.return_value = "listo"
        salida = io.StringIO()
        with patch("builtins.input", side_effect=["armame recetas al excel", "salir"]), redirect_stdout(salida):
            iniciar_chat(rag, GestorRecordatorios(MagicMock()), llm, generador)
        generador.responder.assert_called_once_with("armame recetas al excel")
        rag.invoke.assert_not_called()
        llm.invoke.assert_not_called()  # ni siquiera se gasta la detección de tareas
        self.assertIn("🤖 Asistente: listo", salida.getvalue())


class TestUsuario(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archivo = Path(self.tmp.name) / ".usuario"
        self.addCleanup(self.tmp.cleanup)

    def _obtener(self, entradas=(), usuario_env="", email=""):
        pedir = MagicMock(side_effect=list(entradas))
        with patch.object(config, "ARCHIVO_USUARIO", self.archivo), \
                patch.object(config, "EMAIL_DESTINO", email), \
                patch.dict("os.environ", {"USUARIO": usuario_env}), \
                redirect_stdout(io.StringIO()):
            return config.obtener_usuario(pedir), pedir

    def test_normalizar(self):
        self.assertEqual(config.normalizar_usuario("  Nito Perez "), "nito_perez")
        self.assertEqual(config.normalizar_usuario("Ana@Mail.com"), "ana@mail.com")
        for malo in ["", "a", "nito/../x", "ñandú", "x" * 61]:
            self.assertEqual(config.normalizar_usuario(malo), "", malo)

    def test_prioridad_variable_usuario(self):
        usuario, pedir = self._obtener(usuario_env="Nito", email="otro@mail.com")
        self.assertEqual(usuario, "nito")
        pedir.assert_not_called()

    def test_usa_email_destino(self):
        usuario, pedir = self._obtener(email="Ana@Mail.com")
        self.assertEqual(usuario, "ana@mail.com")
        pedir.assert_not_called()

    def test_pide_y_guarda_la_primera_vez(self):
        usuario, pedir = self._obtener(entradas=["Nito"])
        self.assertEqual(usuario, "nito")
        self.assertEqual(self.archivo.read_text(encoding="utf-8"), "nito")
        # La segunda vez lo lee del archivo y no pregunta.
        usuario, pedir = self._obtener()
        self.assertEqual(usuario, "nito")
        pedir.assert_not_called()

    def test_reintenta_si_el_alias_es_invalido(self):
        usuario, pedir = self._obtener(entradas=["!", "ok_user"])
        self.assertEqual(usuario, "ok_user")
        self.assertEqual(pedir.call_count, 2)

    def test_falla_tras_tres_intentos_invalidos(self):
        with self.assertRaises(ValueError):
            self._obtener(entradas=["!", "?", "x"])


if __name__ == "__main__":
    unittest.main()
