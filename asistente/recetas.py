# -*- coding: utf-8 -*-
"""RECETAS EN GOOGLE SHEETS (vía n8n).

Flujo: el usuario pide recetas ("armame 3 recetas altas en proteína y pasalas
al excel"); la cadena RAG las genera a partir de los PDF en formato JSON y se
envían a n8n con la acción "crear_receta". n8n las separa y agrega una fila por
receta en el Google Sheet (ver docs/contrato_n8n.md).
"""
import json
import re

from .n8n_client import llamar_n8n

MAX_RECETAS = 3
INTENTOS = 3

PATRON_RECETAS = re.compile(r"\brecetas?\b", re.IGNORECASE)
PATRON_ACCION_RECETAS = re.compile(
    r"excel|planilla|sheet|"
    r"arm[aá]|gener[aá]|cre[aá]|hac[eé]me|haceme|dame|pasame|pas[aá]|carg[aá]|"
    r"quiero|necesito|sugerime|suger[ií]",
    re.IGNORECASE,
)

PROMPT_RECETAS = (
    "Eres un asistente de nutrición. Armá recetas usando ÚNICAMENTE el contexto. "
    "Si un dato (calorías, proteínas) no está en el contexto, dejalo como cadena vacía. "
    "No indiques dosis ni prescribas dietas para condiciones médicas. "
    f"Generá como máximo {MAX_RECETAS} recetas. "
    "Respondé SOLO con JSON válido. Reglas del JSON: no uses comillas dobles dentro de los "
    "textos (usá comillas simples), no uses saltos de línea dentro de los valores, "
    "y escribí la preparación en una sola oración corta. "
    'Formato: {{"recetas":[{{"nombre":"","ingredientes":"","calorias":"","proteinas":"","preparacion":""}}]}}'
    "\n\nContexto:\n{context}"
)

CAMPOS = ("nombre", "ingredientes", "calorias", "proteinas", "preparacion")


def detectar_intencion_recetas(texto):
    """True si el mensaje pide generar/cargar recetas (no una simple consulta al RAG)."""
    return bool(PATRON_RECETAS.search(texto) and PATRON_ACCION_RECETAS.search(texto))


def _parsear_recetas(texto):
    """Extrae la lista de recetas del texto del LLM. Devuelve None si no se pudo."""
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    crudo = m.group(0)
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            datos = json.loads(repair_json(crudo))
        except Exception:
            return None
    recetas = datos.get("recetas") if isinstance(datos, dict) else None
    return recetas if isinstance(recetas, list) else None


def _normalizar(recetas):
    """Deja solo los campos del Sheet, siempre como texto, y descarta filas sin nombre."""
    limpias = []
    for r in recetas[:MAX_RECETAS]:
        if not isinstance(r, dict):
            continue
        fila = {c: str(r.get(c, "") or "").strip() for c in CAMPOS}
        if fila["nombre"]:
            limpias.append(fila)
    return limpias


class GeneradorRecetas:
    """Genera recetas con RAG y las manda a n8n para cargarlas en Google Sheets."""

    def __init__(self, llm, retriever):
        from langchain_classic.chains import create_retrieval_chain
        from langchain_classic.chains.combine_documents import create_stuff_documents_chain
        from langchain_core.prompts import ChatPromptTemplate

        # Modo JSON de Groq: obliga al modelo a devolver JSON bien formado.
        llm_json = llm.bind(response_format={"type": "json_object"})
        prompt = ChatPromptTemplate.from_messages([
            ("system", PROMPT_RECETAS),
            ("human", "{input}"),
        ])
        self.chain = create_retrieval_chain(
            retriever, create_stuff_documents_chain(llm_json, prompt)
        )

    def generar(self, pedido, intentos=INTENTOS):
        """Devuelve la lista de recetas o lanza ValueError si el LLM no da JSON válido."""
        for _ in range(intentos):
            respuesta = self.chain.invoke({"input": pedido})
            recetas = _parsear_recetas(respuesta["answer"])
            if recetas:
                recetas = _normalizar(recetas)
                if recetas:
                    return recetas
        raise ValueError("No se pudo obtener un JSON válido de recetas después de varios intentos.")

    def responder(self, pedido):
        """Genera las recetas, las envía a n8n y devuelve el texto para el usuario."""
        try:
            recetas = self.generar(pedido)
        except Exception as e:
            return f"⚠️ No pude generar las recetas: {e}"

        resultado = llamar_n8n("crear_receta", {"recetas": recetas}, timeout=60)
        if resultado.get("success"):
            nombres = ", ".join(r["nombre"] for r in recetas)
            return f"✅ {resultado.get('mensaje', 'Recetas cargadas en el Sheet')}: {nombres}"
        return f"⚠️ No pude cargar las recetas en el Sheet: {resultado.get('mensaje', 'error desconocido')}"