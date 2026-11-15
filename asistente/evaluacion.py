# -*- coding: utf-8 -*-
"""FASE 4: evaluación del sistema contra un dataset de prueba (ground truth).

Parte 1: retriever base (sin traducir). No necesita clave de Groq.
Parte 2: retriever con traducción de la consulta al inglés. Necesita Groq.
Parte 3: abstención en preguntas fuera de dominio. Necesita Groq.

Uso:
    python -m asistente.evaluacion              (retriever + traducción + abstención)
    python -m asistente.evaluacion --sin-llm    (solo retriever base)
    python -m asistente.evaluacion --completa   (abstención también en preguntas del dominio)
"""
import json
import os
import sys
import time

from . import config
from .rag import construir_retriever, retriever_con_traduccion

RUTA_DATASET = config.RAIZ_PROYECTO / "data" / "preguntas_evaluacion.json"

with open(RUTA_DATASET, encoding="utf-8") as f:
    preguntas_evaluacion = json.load(f)

K_LIST = [3, 5, 10]
FRASE_ABSTENCION = "no encuentro"

def _pagina_doc(doc):
    return doc.metadata.get("page", -1) + 1

def _es_relevante(doc, doc_esperado, paginas_esperadas):
    nombre = os.path.basename(doc.metadata.get("source", ""))
    return nombre.lower() == doc_esperado.lower() and _pagina_doc(doc) in paginas_esperadas


def _prom(xs):
    return sum(xs) / len(xs) if xs else 0.0


def evaluar_retrieval(retriever, etiqueta, k_list=K_LIST):
    metricas = {k: {"hit": [], "mrr": [], "precision": [], "recall": [], "kw": []} for k in k_list}
    con_respuesta = [q for q in preguntas_evaluacion if q["documento_esperado"] is not None]

    print(f"\n--- {etiqueta}: hit por pregunta (página exacta) ---")
    for q in con_respuesta:
        docs = retriever.invoke(q["pregunta"])
        esperado, paginas = q["documento_esperado"], q["paginas_esperadas"]

        linea = [f"  {q['pregunta']}"]
        for k in k_list:
            top = docs[:k]
            flags = [_es_relevante(d, esperado, paginas) for d in top]

            posicion = next((i for i, fl in enumerate(flags, start=1) if fl), None)
            hit = 1 if posicion else 0
            mrr = 1.0 / posicion if posicion else 0.0
            precision = sum(flags) / len(top) if top else 0.0
            encontradas = {_pagina_doc(d) for d, fl in zip(top, flags) if fl}
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

    print("\n==========================================")
    print(f"📊 RESUMEN: {etiqueta}")
    print(f"   ({len(con_respuesta)} preguntas con respuesta en los documentos)")
    print("==========================================")
    for k in k_list:
        m = metricas[k]
        print(f"📌 K = {k}")
        print(f"   • Hit Rate @ {k}:   {_prom(m['hit']):.2%}")
        print(f"   • MRR @ {k}:        {_prom(m['mrr']):.2f}")
        print(f"   • Precision @ {k}:  {_prom(m['precision']):.2%}")
        print(f"   • Recall @ {k}:     {_prom(m['recall']):.2%}")
        print(f"   • Keywords @ {k}:   {_prom(m['kw']):.2%}")
        print("-" * 42)

    return {k: {n: _prom(v) for n, v in metricas[k].items()} for k in k_list}


def comparar(base, traducido):
    print("\n==========================================")
    print("🔁 COMPARACIÓN: base vs. con traducción")
    print("==========================================")
    print(f"{'k':<4}{'Hit base':>10}{'Hit trad.':>11}{'MRR base':>10}{'MRR trad.':>11}")
    for k in base:
        print(f"{k:<4}{base[k]['hit']:>10.0%}{traducido[k]['hit']:>11.0%}"
              f"{base[k]['mrr']:>10.2f}{traducido[k]['mrr']:>11.2f}")

def _invocar_con_reintento(chain, entrada, intentos=4):
    """Si Groq devuelve límite de tokens (429), espera y reintenta."""
    for i in range(intentos):
        try:
            return chain.invoke(entrada)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                espera = 20 * (i + 1)
                print(f"   ⏳ Límite de Groq, espero {espera}s...")
                time.sleep(espera)
            else:
                raise
    raise RuntimeError("Groq siguió rechazando las llamadas.")


def evaluar_abstencion(retriever_chat, llm):
    """Cadena RAG completa, igual a la del chat real (con traducción).

    Por defecto solo evalúa las preguntas fuera de dominio (menos tokens).
    Con --completa evalúa también las del dominio (abstenciones indebidas).
    """
    from .llm import crear_rag_chain

    rag_chain = crear_rag_chain(llm, retriever_chat)
    abst_ok = fuera = falsas_abst = dentro = 0

    print("\n==========================================")
    print("🚫 EVALUACIÓN DE ABSTENCIÓN (con LLM)")
    print("==========================================")
    for q in preguntas_evaluacion:
        if q["documento_esperado"] is not None and "--completa" not in sys.argv:
            continue

        respuesta = _invocar_con_reintento(rag_chain, {"input": q["pregunta"]})["answer"]
        time.sleep(3)
        se_abstuvo = FRASE_ABSTENCION in respuesta.lower()

        if q["documento_esperado"] is None:
            fuera += 1
            abst_ok += se_abstuvo
            print(f"{'✅' if se_abstuvo else '❌'} [fuera de dominio] {q['pregunta']}")
            if not se_abstuvo:
                print(f"     Respuesta: {respuesta[:200]}")
        else:
            dentro += 1
            falsas_abst += se_abstuvo
            print(f"{'⚠️ se abstuvo' if se_abstuvo else '✅'} [en dominio] {q['pregunta']}")

    print("-" * 42)
    if fuera:
        print(f"Abstención correcta (fuera de dominio): {abst_ok}/{fuera} = {abst_ok / fuera:.0%}")
    if dentro:
        print(f"Abstenciones indebidas (en dominio):    {falsas_abst}/{dentro} = {falsas_abst / dentro:.0%}")


def main():
    solo_base = "--sin-llm" in sys.argv

    try:
        # k=10 para medir @3, @5 y @10 con una sola recuperación por pregunta.
        retriever = construir_retriever(k=max(K_LIST))
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        sys.exit(1)

    base = evaluar_retrieval(retriever, "BASE (sin traducir)")

    if solo_base:
        return

    try:
        from .llm import crear_llm

        config.obtener_api_key()
        llm = crear_llm()

        traducido = evaluar_retrieval(retriever_con_traduccion(retriever, llm),
                                      "CON TRADUCCIÓN al inglés")
        comparar(base, traducido)

        # Mismo k que el chat real, sin reindexar los PDF.
        retriever_chat = retriever_con_traduccion(
            retriever.vectorstore.as_retriever(search_kwargs={"k": config.RETRIEVER_K}), llm)
        evaluar_abstencion(retriever_chat, llm)
    except (ValueError, ModuleNotFoundError) as e:
        print(f"⚠️ No se pudo completar la evaluación con LLM: {e}")


if __name__ == "__main__":
    main()