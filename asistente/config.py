# -*- coding: utf-8 -*-
"""Configuración central del asistente.

Equivale a las celdas "CONFIGURACIÓN DE CLAVES Y RUTAS" y a los parámetros
sueltos del notebook original (chunk_size, k, modelo, etc.).

Los valores que cambian según quién ejecuta el proyecto (clave, webhook, correo,
PDFs) se pueden definir en un archivo `.env` en la raíz del proyecto o como
variables de entorno. Si no se definen, se usan los mismos valores por defecto
que tenía el notebook.
"""
import os
from getpass import getpass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv es opcional: sin él solo se leen variables de entorno reales
    load_dotenv = None

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    # Ruta explícita: funciona aunque se ejecute desde otra carpeta.
    load_dotenv(RAIZ_PROYECTO / ".env")

# ------------------------------------------------------------------
# n8n
# ------------------------------------------------------------------
# URL del webhook de n8n. IMPORTANTE: los recordatorios quedan esperando en n8n
# (nodo Wait). Eso solo funciona con el workflow ACTIVADO y la URL de producción
# (/webhook/...), no con la URL de prueba (/webhook-test/...).
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "",
)

# Valor del campo "origen" que se envía a n8n. Se conserva "Colab_IA2" tal cual
# estaba en el notebook porque el workflow de n8n podría depender de él.
N8N_ORIGEN = "Colab_IA2"

# Correo de destino de los recordatorios (opcional).
# Si queda vacío, n8n usa el correo por defecto configurado en el nodo Gmail.
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO", "")

# ------------------------------------------------------------------
# Documentos (RAG)
# ------------------------------------------------------------------
_PDFS_POR_DEFECTO = ["data/LIBRO1.pdf", "data/LIBRO2.pdf"]


def _resolver_pdfs():
    """Lista de PDFs a indexar. Rutas relativas = relativas a la raíz del proyecto."""
    crudo = os.getenv("PDF_PATHS", "")
    nombres = [p.strip() for p in crudo.split(",") if p.strip()] or _PDFS_POR_DEFECTO
    return [str(Path(p) if Path(p).is_absolute() else RAIZ_PROYECTO / p) for p in nombres]


PDF_PATHS = _resolver_pdfs()

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVER_K = 5

# Embeddings. El notebook dejó como activo el baseline multilingüe y comentado
# el modelo experimental "linhha2705/multilingual-e5-nutrition".
# Para probar el experimental: EMBEDDING_MODEL=linhha2705/multilingual-e5-nutrition
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

# ------------------------------------------------------------------
# LLM (Groq)
# ------------------------------------------------------------------
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
LLM_TEMPERATURE = 0.2


def obtener_api_key():
    """Deja la clave de Groq disponible en os.environ["GROQ_API_KEY"] y la devuelve.

    El notebook siempre la pedía con getpass. Acá se usa primero la que ya esté
    definida (entorno o archivo .env) y, si no hay ninguna, se pide por consola
    con getpass, igual que antes.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    if not api_key:
        api_key = getpass("Ingrese la API key de Groq: ").strip()

    if not api_key:
        raise ValueError("No ingresaste ninguna API Key.")

    os.environ["GROQ_API_KEY"] = api_key
    return api_key
