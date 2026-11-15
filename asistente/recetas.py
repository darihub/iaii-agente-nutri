# -*- coding: utf-8 -*-
"""RECETAS EN GOOGLE SHEETS, UN EXCEL POR USUARIO (vía n8n).

Flujo: el usuario pide recetas ("armame 3 recetas altas en proteína y pasalas
al excel"); la cadena RAG las genera a partir de los PDF en formato JSON y se
envían a n8n con la acción "crear_receta" junto con el identificador del
usuario. n8n busca (o crea) el Google Sheet de ese usuario, agrega una fila por
receta y devuelve el link del archivo (ver docs/n8n_recetas_por_usuario.md).

Si algo sale mal, el mensaje distingue tres casos: el modelo no devolvió JSON
válido, no encontró recetas para ese pedido, o n8n falló.
"""
import json
import os
import re

from . import config
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

# Se antepone al pedido para que la búsqueda en los PDF traiga fragmentos de
# recetas (ingredientes y preparación) aunque el pedido sea vago ("para cuidarme").
PREFIJO_CONSULTA = "Receta con ingredientes y preparación. Pedido: "

PROMPT_RECETAS = (
    "Eres un asistente de nutrición. Armá recetas usando ÚNICAMENTE el contexto. "
    "Si el pedido es general (por ejemplo 'para cuidarme' o 'algo saludable'), armá recetas "
    "simples y equilibradas con los alimentos y criterios que aparezcan en el contexto. "
    "Si un dato (calorías, proteínas) no está en el contexto, dejalo como cadena vacía. "
    "No indiques dosis ni prescribas dietas para condiciones médicas. "
    f"Generá como máximo {MAX_RECETAS} recetas. "
    'Si el contexto no tiene nada útil para armar una receta, devolvé {{"recetas":[]}}. '
    "Respondé SOLO con JSON válido. Reglas del JSON: no uses comillas dobles dentro de los "
    "textos (usá comillas simples), no uses saltos de línea dentro de los valores, "
    "y escribí la preparación en una sola oración corta. "
    'Formato: {{"recetas":[{{"nombre":"","ingredientes":"","calorias":"","proteinas":"","preparacion":""}}]}}'
    "\n\nContexto:\n{context}"
)

CAMPOS = ("nombre", "ingredientes", "calorias", "proteinas", "preparacion")

MSG_SIN_RECETAS = (
    "No encontré recetas para ese pedido en los documentos. "
    "Probá con algo más concreto, por ejemplo: 'armame 2 recetas altas en proteína'."
)


class SinRecetas(ValueError):
    """El modelo devolvió JSON válido pero sin ninguna receta."""


def detectar_intencion_recetas(texto):
    """True si el mensaje pide generar/cargar recetas (no una simple consulta al RAG)."""
    return bool(PATRON_RECETAS.search(texto) and PATRON_ACCION_RECETAS.search(texto))


def _parsear_recetas(texto):
    """Extrae la lista de recetas del texto del LLM.

    Devuelve None si no hay JSON utilizable y una lista (posiblemente vacía)
    si el JSON es válido."""
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
    """Genera recetas con RAG y las manda a n8n para cargarlas en el Sheet del usuario."""

    def __init__(self, llm, retriever, usuario=""):
        from langchain_classic.chains import create_retrieval_chain
        from langchain_classic.chains.combine_documents import create_stuff_documents_chain
        from langchain_core.prompts import ChatPromptTemplate

        self.usuario = usuario

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
        """Devuelve la lista de recetas.

        Lanza SinRecetas si el modelo no encontró nada y ValueError si nunca
        devolvió un JSON válido."""
        consulta = f"{PREFIJO_CONSULTA}{pedido}"
        hubo_json_vacio = False
        ultimo = ""
        for _ in range(intentos):
            respuesta = self.chain.invoke({"input": consulta})
            ultimo = respuesta["answer"]
            recetas = _parsear_recetas(ultimo)
            if recetas is None:
                continue
            limpias = _normalizar(recetas)
            if limpias:
                return limpias
            hubo_json_vacio = True

        if os.getenv("RECETAS_DEBUG"):
            print(f"[RECETAS_DEBUG] última respuesta cruda del modelo:\n{ultimo}")
        if hubo_json_vacio:
            raise SinRecetas(MSG_SIN_RECETAS)
        raise ValueError("el modelo no devolvió un JSON válido después de varios intentos")

    def responder(self, pedido):
        """Genera las recetas, las envía a n8n y devuelve el texto para el usuario."""
        try:
            recetas = self.generar(pedido)
        except SinRecetas as e:
            return f"ℹ️ {e}"
        except Exception as e:
            return f"⚠️ No pude generar las recetas: {e}"

        resultado = llamar_n8n("crear_receta", self._datos_para_n8n(recetas, pedido), timeout=90)
        if not resultado.get("success"):
            return f"⚠️ No pude cargar las recetas en el Sheet: {resultado.get('mensaje', 'error desconocido')}"

        nombres = ", ".join(r["nombre"] for r in recetas)
        texto = f"✅ {resultado.get('mensaje', 'Recetas cargadas en el Sheet')}: {nombres}"
        if resultado.get("url"):
            texto += f"\n📄 Tu Excel: {resultado['url']}"
        return texto

    def _detectar_categoria(self, pedido):
        """Extrae una categoría simple del pedido para usarla como pestaña en el Excel."""
        pedido_lower = (pedido or "").lower()
        if "proteína" in pedido_lower or "proteinas" in pedido_lower or "proteico" in pedido_lower:
            return "Altas en Proteína"
        elif "déficit" in pedido_lower or "calorico" in pedido_lower or "bajar" in pedido_lower or "peso" in pedido_lower:
            return "Déficit Calórico"
        elif "vegano" in pedido_lower or "vegetariano" in pedido_lower:
            return "Vegetariano - Vegano"
        elif "keto" in pedido_lower or "cetogenica" in pedido_lower:
            return "Keto"
        return "Recetas Generales"

    def _datos_para_n8n(self, recetas, pedido=""):
        usuario = self.usuario or config.EMAIL_DESTINO
        email = usuario if "@" in usuario else (config.EMAIL_DESTINO or usuario)
        categoria = self._detectar_categoria(pedido)
        return {
            "usuario": usuario,
            "email": email,
            "categoria": categoria,
            "recetas": recetas,
        }