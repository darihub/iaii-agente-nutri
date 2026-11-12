# -*- coding: utf-8 -*-
"""Orquesta el arranque del asistente, en el mismo orden que el notebook:

  1. Clave de Groq
  2. PDF -> fragmentos -> embeddings -> retriever      (rag.py)
  3. LLM + cadena RAG                                  (llm.py)
  4. Gestor de recordatorios                           (recordatorios.py)
  5. Bucle de chat                                     (chat.py)
"""
import sys

from . import config


def main():
    try:
        config.obtener_api_key()

        # Los imports pesados (LangChain, modelos) se hacen después de pedir la
        # clave: si falta, el error aparece enseguida y no tras varios segundos de carga.
        from .chat import iniciar_chat
        from .llm import crear_llm, crear_rag_chain
        from .rag import construir_retriever
        from .recordatorios import GestorRecordatorios

        retriever = construir_retriever()
        llm = crear_llm()
        rag_chain = crear_rag_chain(llm, retriever)
        gestor = GestorRecordatorios(llm)
    except ModuleNotFoundError as e:
        print(f"⚠️ Falta instalar una dependencia ({e.name}). Ejecutá: pip install -r requirements.txt")
        sys.exit(1)
    except (ValueError, FileNotFoundError) as e:
        print(f"⚠️ {e}")
        sys.exit(1)

    iniciar_chat(rag_chain, gestor,llm)


if __name__ == "__main__":
    main()
