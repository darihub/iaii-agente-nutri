# -*- coding: utf-8 -*-
"""FASE 4: herramienta de evaluación del retriever.

Muestra qué fragmentos recupera el sistema para una pregunta, con sus metadatos
(documento y página), para comprobar que realmente provienen del PDF y responden
a la consulta. No usa el LLM, así que NO necesita clave de Groq.

Uso:
    python -m asistente.evaluacion "¿Qué es la fibra dietaria?"
    python -m asistente.evaluacion            (pide la pregunta por consola)
"""
import sys

from .rag import construir_retriever


def main():
    pregunta_prueba = " ".join(sys.argv[1:]).strip() or input("Pregunta de evaluación: ").strip()
    if not pregunta_prueba:
        print("No ingresaste ninguna pregunta.")
        return

    try:
        retriever = construir_retriever()
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        sys.exit(1)

    docs = retriever.invoke(pregunta_prueba)
    for i, doc in enumerate(docs, start=1):
        print(f"\n====== FRAGMENTO {i} ======")
        print("Metadatos:", doc.metadata)
        print(doc.page_content)


if __name__ == "__main__":
    main()
