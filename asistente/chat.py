# -*- coding: utf-8 -*-
"""Bucle de chat por consola."""

from .n8n_client import enviar_a_n8n_test
from .prompts import AVISO_PERMANENTE
from .recordatorios import detectar_intencion_recordatorio
from .tareas import detectar_intencion_tarea
from .recetas import detectar_intencion_recetas

PALABRAS_PRUEBA_N8N = ["prueban8n"]


def iniciar_chat(rag_chain, gestor_recordatorios, llm, generador_recetas=None):
    print("\n🤖 Asistente iniciado. Escribí 'salir' para terminar.")
    print(AVISO_PERMANENTE)
    print("-" * 50)
    historial = []

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

        if any(palabra in pregunta.lower() for palabra in PALABRAS_PRUEBA_N8N):
            print("🤖 Asistente: Ejecutando prueba de Tasks de n8n...")
            resultado_n8n = enviar_a_n8n_test({"accion": "crear_tarea"})
            print(f"⚙️ Sistema: {resultado_n8n}")
            print("-" * 50)
            continue

        # Recetas: se generan con RAG y se cargan en un Google Sheet vía n8n.
        if generador_recetas is not None and detectar_intencion_recetas(pregunta):
            print("🤖 Asistente: Armando las recetas con tus documentos...")
            print(f"🤖 Asistente: {generador_recetas.responder(pregunta)}")
            print("-" * 50)
            continue

        intencion_tarea = detectar_intencion_tarea(pregunta, llm, historial)
        if intencion_tarea["accion"] == "crear_tarea":
            print("🤖 Asistente: Creando tarea en Google Tasks...")
            resultado_n8n = enviar_a_n8n_test(intencion_tarea)
            print(f"⚙️ Sistema: {resultado_n8n}")
            historial.append({
                "usuario": pregunta,
                "asistente": resultado_n8n,
            })
            print("-" * 50)
            continue

        # Si no es una acción, consultamos los documentos mediante RAG.
        try:
            respuesta = rag_chain.invoke({"input": pregunta})
            texto_respuesta = respuesta["answer"]

            print(f"🤖 Asistente: {respuesta['answer']}")

            historial.append({
                "usuario": pregunta,
                "asistente": texto_respuesta
            })

        except Exception as e:
            print(f"⚠️ Ocurrió un error al consultar el asistente: {e}")

        print("-" * 50)
