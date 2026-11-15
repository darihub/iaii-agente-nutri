# -*- coding: utf-8 -*-
"""FASE 2: Memoria y conocimiento privado.

Carga los PDF, los divide en fragmentos, genera los embeddings y arma el
retriever sobre una base vectorial Chroma (en memoria, igual que en el notebook:
se reconstruye en cada ejecución).
"""
import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "chroma_db"

from . import config


def cargar_documentos(pdf_paths=None):
    """Lee todas las páginas de los PDF indicados."""
    pdf_paths = pdf_paths if pdf_paths is not None else config.PDF_PATHS

    print("Cargando los documentos PDF...")

    documentos = []
    for ruta_pdf in pdf_paths:
        if not os.path.isfile(ruta_pdf):
            raise FileNotFoundError(
                f"No se encontró el PDF: {ruta_pdf}\n"
                "Revisá PDF_PATHS en asistente/config.py o en tu archivo .env "
                "(los PDF van en la carpeta data/)."
            )
        documentos.extend(PyPDFLoader(ruta_pdf).load())

    print(f"Documentos cargados: {len(documentos)} páginas")
    return documentos


def dividir_documentos(documentos):
    """Divide las páginas en fragmentos (chunks) para indexar."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    textos_divididos = text_splitter.split_documents(documentos)
    print(f"Fragmentos generados: {len(textos_divididos)}")
    return textos_divididos


def crear_retriever(textos_divididos, k=None):
    """Genera los embeddings, arma la base vectorial y devuelve el retriever."""
    modelo_embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)

    if DB_PATH.exists() and any(DB_PATH.iterdir()):
        print("Cargando base vectorial existente...")
        print(" (si se cambia algun documento, borrar la carpeta chroma db)")

        vectorstore = Chroma(
            persist_directory=str(DB_PATH),
            embedding_function=modelo_embeddings
        )

    else:
        print("Generando base vectorial por primera vez...")

        vectorstore = Chroma.from_documents(
            documents=textos_divididos,
            embedding=modelo_embeddings,
            persist_directory=str(DB_PATH)
        )

    retriever = vectorstore.as_retriever(search_kwargs={"k": k or config.RETRIEVER_K})
    print("PDFs cargados y retriever configurado.")
    return retriever

def construir_retriever(pdf_paths=None, k=None):
    """Pipeline completo: PDF -> fragmentos -> embeddings -> retriever."""
    documentos = cargar_documentos(pdf_paths)
    textos_divididos = dividir_documentos(documentos)
    return crear_retriever(textos_divididos, k=k)

def retriever_con_traduccion(retriever, llm):
    """Traduce la consulta al inglés antes de buscar, porque los PDF están en inglés.

    Si la traducción falla, busca con la pregunta original.
    Cachea las traducciones para no repetir llamadas al LLM.
    """
    cache = {}

    def _buscar(pregunta):
        if isinstance(pregunta, dict):
            pregunta = pregunta.get("input", "")
        if pregunta not in cache:
            try:
                respuesta = llm.invoke([
                    ("system", "Traducí la consulta del usuario al inglés. "
                               "Respondé solo con la traducción, sin comillas ni explicaciones."),
                    ("human", pregunta),
                ])
                cache[pregunta] = str(respuesta.content).strip() or pregunta
            except Exception as e:
                print(f"No pude traducir la consulta ({e}). Uso la original.")
                cache[pregunta] = pregunta
        return retriever.invoke(cache[pregunta])

    return RunnableLambda(_buscar)
