# -*- coding: utf-8 -*-
"""Bucle de chat por consola.

Orden de decisión por cada mensaje (idéntico al notebook):
  1. "salir" / "exit"            -> termina.
  2. Recordatorio (en curso o nuevo) -> GestorRecordatorios.
  3. "turno" / "agendar" / "reservar" -> envía el mensaje a n8n.
  4. "prueban8n"                 -> prueba fija de Google Tasks en n8n.
  5. Cualquier otra cosa         -> consulta RAG sobre los PDF.
"""
from .n8n_client import enviar_a_n8n, enviar_a_n8n_test
from .prompts import AVISO_PERMANENTE
from .recordatorios import detectar_intencion_recordatorio

PALABRAS_TURNO = ["turno", "agendar", "reservar"]
PALABRAS_PRUEBA_N8N = ["prueban8n"]


def iniciar_chat(rag_chain, gestor_recordatorios):
    print("\n🤖 Asistente iniciado. Escribí 'salir' para terminar.")
    print(AVISO_PERMANENTE)
    print("-" * 50)

    while True:
        try:
            pregunta = input("👤 Vos: ").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C / Ctrl+D: salida limpia en lugar de un traceback.
            print("\n🤖 Asistente: ¡Nos vemos!")
            break

        if pregunta.lower() in ["salir", "exit"]:
            print("🤖 Asistente: ¡Nos vemos!")
            break

        if not pregunta:
            continue

        # Recordatorios por correo (se evalúa primero para no chocar con otras palabras clave).
        # Si hay un recordatorio a medio completar, el mensaje se interpreta como respuesta a ese pedido.
        if gestor_recordatorios.hay_pendiente() or detectar_intencion_recordatorio(pregunta):
            print(f"🤖 Asistente: {gestor_recordatorios.responder(pregunta)}")
            print("-" * 50)
            continue

        # Lógica simple para disparar n8n cuando se detecta una intención de turno.
        if any(palabra in pregunta.lower() for palabra in PALABRAS_TURNO):
            print("🤖 Asistente: Detecté que querés agendar un turno. Avisando al sistema...")
            resultado_n8n = enviar_a_n8n(pregunta)
            print(f"⚙️ Sistema: {resultado_n8n}")
            continue

        if any(palabra in pregunta.lower() for palabra in PALABRAS_PRUEBA_N8N):
            print("🤖 Asistente: Ejecutando prueba de Tasks de n8n...")
            enviar_a_n8n_test(pregunta)
            continue

        # Si no es una acción, consultamos los documentos mediante RAG.
        try:
            respuesta = rag_chain.invoke({"input": pregunta})
            print(f"🤖 Asistente: {respuesta['answer']}")
        except Exception as e:
            print(f"⚠️ Ocurrió un error al consultar el asistente: {e}")

        print("-" * 50)
