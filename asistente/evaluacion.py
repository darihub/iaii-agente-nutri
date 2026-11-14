# -*- coding: utf-8 -*-
"""FASE 4: evaluación del sistema contra un dataset de prueba (ground truth).

Parte 1 (retriever): Hit Rate, MRR, Precision y Recall @k, más cobertura de
palabras clave. No necesita clave de Groq.
Parte 2 (abstención): usa el LLM para ver si responde "no encuentro" en las
preguntas fuera de dominio y NO se abstiene en las del dominio. Necesita clave
de Groq.

Uso:
    python -m asistente.evaluacion              (retriever + abstención)
    python -m asistente.evaluacion --sin-llm    (solo retriever)
"""
import json
import os
import sys

from . import config
from .rag import construir_retriever

RUTA_DATASET = config.RAIZ_PROYECTO / "data" / "preguntas_evaluacion.json"

with open(RUTA_DATASET, encoding="utf-8") as f:
    preguntas_evaluacion = json.load(f)

K_LIST = [3, 5, 10]
FRASE_ABSTENCION = "no encuentro"


def _es_relevante(doc, doc_esperado, paginas_esperadas):
    """Mismo documento y misma página (PyPDFLoader numera desde 0, el dataset desde 1)."""
    nombre = os.path.basename(doc.metadata.get("source", ""))
    pagina = doc.metadata.get("page", -1) + 1
    return nombre.lower() == doc_esperado.lower() and pagina in paginas_esperadas


def _pagina_doc(doc):
    return doc.metadata.get("page", -1) + 1


def evaluar_retrieval(retriever, k_list=K_LIST):
    metricas = {k: {"hit": [], "mrr": [], "precision": [], "recall": [], "kw": []} for k in k_list}
    con_respuesta = [q for q in preguntas_evaluacion if q["documento_esperado"] is not None]

    for q in con_respuesta:
        docs = retriever.invoke(q["pregunta"])
        esperado, paginas = q["documento_esperado"], q["paginas_esperadas"]

        linea = [f"  {q['pregunta']}"]
        for k in k_list:
            top = docs[:k]
            flags = [_es_relevante(d, esperado, paginas) for d in top]

            posicion = next((i for i, f in enumerate(flags, start=1) if f), None)
            hit = 1 if posicion else 0
            mrr = 1.0 / posicion if posicion else 0.0
            precision = sum(flags) / len(top) if top else 0.0
            encontradas = {_pagina_doc(d) for d, f in zip(top, flags) if f}
            recall = len(encontradas) / len(paginas)

            texto = " ".join(d.page_content for d in top).lower()
            kws = q["palabras_clave_esperadas"]
            kw = sum(w.lower() in texto for w in kws) / len(kws) if kws else 1.0

            metricas[k]["hit"].append(hit)
            metricas[k]["mrr"].append(mrr)
            metricas[k]["precision"].append(precision)
            metricas[k]["recall"].append(recall)
            metricas[k]["kw"].append(kw)
            linea.append(f"k={k}:{'✅' if hit else '❌'}")
        print("  ".join(linea))

    def prom(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print("\n==========================================")
    print("📊 RESUMEN DE MÉTRICAS DE RECUPERACIÓN")
    print(f"   ({len(con_respuesta)} preguntas con respuesta en los documentos)")
    print("==========================================")
    for k in k_list:
        m = metricas[k]
        print(f"📌 K = {k}")
        print(f"   • Hit Rate @ {k}:   {prom(m['hit']):.2%}")
        print(f"   • MRR @ {k}:        {prom(m['mrr']):.2f}")
        print(f"   • Precision @ {k}:  {prom(m['precision']):.2%}")
        print(f"   • Recall @ {k}:     {prom(m['recall']):.2%}")
        print(f"   • Keywords @ {k}:   {prom(m['kw']):.2%}")
        print("-" * 42)


def evaluar_abstencion(retriever):
    """Llama a la cadena RAG completa (necesita clave de Groq)."""
    from .llm import crear_llm, crear_rag_chain

    config.obtener_api_key()
    # Mismo k que usa el chat real, sin reindexar los PDF.
    retriever_chat = retriever.vectorstore.as_retriever(search_kwargs={"k": config.RETRIEVER_K})
    rag_chain = crear_rag_chain(crear_llm(), retriever_chat)

    abst_ok = fuera = 0
    falsas_abst = dentro = 0

    print("\n==========================================")
    print("🚫 EVALUACIÓN DE ABSTENCIÓN (con LLM)")
    print("==========================================")
    for q in preguntas_evaluacion:
        respuesta = rag_chain.invoke({"input": q["pregunta"]})["answer"]
        se_abstuvo = FRASE_ABSTENCION in respuesta.lower()

        if q["documento_esperado"] is None:
            fuera += 1
            abst_ok += se_abstuvo
            print(f"{'✅' if se_abstuvo else '❌'} [fuera de dominio] {q['pregunta']}")
        else:
            dentro += 1
            falsas_abst += se_abstuvo
            print(f"{'⚠️ se abstuvo' if se_abstuvo else '✅'} [en dominio] {q['pregunta']}")
        if not se_abstuvo and q["documento_esperado"] is None:
            print(f"     Respuesta: {respuesta[:200]}")

    print("-" * 42)
    print(f"Abstención correcta (fuera de dominio): {abst_ok}/{fuera} = {abst_ok / fuera:.0%}")
    print(f"Abstenciones indebidas (en dominio):    {falsas_abst}/{dentro} = {falsas_abst / dentro:.0%}")


def main():
    solo_retriever = "--sin-llm" in sys.argv

    try:
        # k=10 para poder medir @3, @5 y @10 con una sola recuperación por pregunta.
        retriever = construir_retriever(k=max(K_LIST))
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        sys.exit(1)

    print("\n--- Hit por pregunta (página exacta) ---")
    evaluar_retrieval(retriever)

    if not solo_retriever:
        try:
            evaluar_abstencion(retriever)
        except (ValueError, ModuleNotFoundError) as e:
            print(f"⚠️ No se pudo evaluar la abstención: {e}")


if __name__ == "__main__":
    main()