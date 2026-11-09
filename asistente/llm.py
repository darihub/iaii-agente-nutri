# -*- coding: utf-8 -*-
"""Configuración del LLM (Groq) y de la cadena RAG de LangChain."""
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from . import config
from .prompts import SYSTEM_PROMPT


def crear_llm():
    """Crea el cliente de Groq. Requiere GROQ_API_KEY en el entorno."""
    return ChatGroq(model_name=config.GROQ_MODEL, temperature=config.LLM_TEMPERATURE)


def crear_rag_chain(llm, retriever):
    """Cadena RAG: pregunta -> busca fragmentos -> LLM responde con ese contexto."""
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt_template)
    return create_retrieval_chain(retriever, question_answer_chain)
