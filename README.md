# Asistente Virtual Inteligente de Nutrición (LLM + RAG + n8n)

Chatbot de consola para orientación general en nutrición y alimentación.
Proyecto integrador de **Inteligencia Artificial 2 – UAA (Grupo 5)**.

El asistente hace tres cosas:

1. **Responde consultas sobre tus PDF (RAG).** Busca los fragmentos más relevantes
   en una base vectorial (Chroma) y le pide a un LLM (Groq · `openai/gpt-oss-20b`)
   que responda **solo** con esa información.
2. **Programa recordatorios por correo.** Entiende pedidos en lenguaje natural
   ("recordame tomar agua mañana a las 8, 3 veces"), pregunta lo que falte y
   delega el envío a un workflow de **n8n** (Gmail).
3. **Dispara acciones en n8n:** recetas por Google Sheets y una prueba de Google Tasks.

> ⚠️ Información general de carácter educativo. No reemplaza la consulta con un profesional de la salud.
> Los límites de seguridad del asistente están en [`docs/limites_seguridad.md`](docs/limites_seguridad.md).

---

## Estructura del proyecto

```
asistente-nutricional-rag/
├── main.py                  # Punto de entrada:  python main.py
├── requirements.txt         # Dependencias
├── .env.example             # Plantilla de configuración (copiar a .env)
├── .gitignore
├── README.md
│
├── asistente/               # Paquete con todo el código
│   ├── __main__.py          #   permite:  python -m asistente
│   ├── app.py               #   orquesta el arranque (el "main")
│   ├── config.py            #   claves, URL de n8n, rutas de PDF, parámetros
│   ├── prompts.py           #   system prompt y aviso legal (FASE 1)
│   ├── rag.py               #   PDF → fragmentos → embeddings → retriever (FASE 2)
│   ├── llm.py               #   cliente Groq + cadena RAG de LangChain
│   ├── n8n_client.py        #   conexión con los webhooks de n8n (FASE 3)
│   ├── recordatorios.py     #   conversación de recordatorios (FASE 3)
│   ├── chat.py              #   bucle de chat y enrutado de mensajes
│   └── evaluacion.py        #   inspección de fragmentos recuperados (FASE 4)
│
├── data/                    # Acá van tus PDF (no se suben a GitHub)
├── docs/                    # Descripción del proyecto, límites, contrato n8n, evaluación
└── tests/                   # Pruebas automáticas (unittest)
```

### Cómo se relaciona con el notebook original

| Celda del notebook | Ahora vive en |
|---|---|
| Fase 1 (diseño, personalidad) + system prompt | `asistente/prompts.py` |
| Límites y criterios de seguridad (markdown) | `docs/limites_seguridad.md` |
| `pip install` + imports | `requirements.txt` + imports de cada módulo |
| Claves y rutas (`getpass`, webhook, PDF) | `asistente/config.py` + `.env` |
| Procesamiento de PDF (RAG) | `asistente/rag.py` |
| Configuración del LLM y `rag_chain` | `asistente/llm.py` |
| `enviar_a_n8n`, `enviar_a_n8n_test` | `asistente/n8n_client.py` |
| Recordatorios por Gmail | `asistente/recordatorios.py` (+ `llamar_n8n` en `n8n_client.py`) |
| Bucle de chat | `asistente/chat.py` |
| Fase 4 (evaluación) | `asistente/evaluacion.py` + `docs/evaluacion.md` |

### Flujo de una ejecución

```
python main.py
   └─ app.main()
        1. config.obtener_api_key()      → clave de Groq (.env, entorno o getpass)
        2. rag.construir_retriever()     → lee PDF, fragmenta, embeddings, Chroma
        3. llm.crear_llm() / crear_rag_chain()
        4. GestorRecordatorios(llm)
        5. chat.iniciar_chat(...)        → bucle de conversación
```

Por cada mensaje, `chat.py` decide en este orden:

1. `salir` / `exit` → termina.
2. ¿Hay un recordatorio a medio completar, o el texto pide uno? → `GestorRecordatorios`.
3. ¿Contiene `turno`, `agendar` o `reservar`? → se envía a n8n.
4. ¿Contiene `prueban8n`? → prueba fija de Google Tasks en n8n.
5. Cualquier otra cosa → consulta RAG sobre los PDF.

---

## Requisitos

- **Python 3.10 o superior** (el notebook original corría en Python 3.12).
- Una **API key de Groq** (gratis): <https://console.groq.com> → *API Keys* → *Create API Key* (empieza con `gsk_`).
- **Tus PDF** (por defecto `LIBRO1.pdf` y `LIBRO2.pdf`).
- *(Opcional)* Un workflow de **n8n** si querés usar recordatorios, turnos o Tasks.
  Ver [`docs/contrato_n8n.md`](docs/contrato_n8n.md).
- Conexión a internet: Groq es una API en la nube, y la primera ejecución descarga el
  modelo de embeddings desde Hugging Face (cientos de MB; después queda en caché).

## Instalación

```bash
git clone <URL-de-tu-repositorio>
cd asistente-nutricional-rag

# 1) Entorno virtual
python -m venv .venv

# Activarlo:
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   Windows (cmd):         .venv\Scripts\activate.bat
#   macOS / Linux:         source .venv/bin/activate

# 2) Dependencias (la primera vez tarda varios minutos: incluye PyTorch)
pip install -r requirements.txt
```

## Configuración

1. **Copiá la plantilla** `.env.example` como `.env` y completá lo que necesites:

   ```bash
   cp .env.example .env          # Windows: copy .env.example .env
   ```

   | Variable | Para qué sirve | Si no la definís |
   |---|---|---|
   | `GROQ_API_KEY` | Clave de Groq | El programa la pide al iniciar (como en el notebook) |
   | `N8N_WEBHOOK_URL` | Webhook de n8n | Usa la URL de prueba que tenía el notebook |
   | `EMAIL_DESTINO` | Destinatario de recordatorios | Usa el correo del nodo Gmail de n8n |
   | `PDF_PATHS` | PDF a indexar, separados por coma | `data/LIBRO1.pdf,data/LIBRO2.pdf` |
   | `GROQ_MODEL` | Modelo de Groq | `openai/gpt-oss-20b` |
   | `EMBEDDING_MODEL` | Modelo de embeddings | `paraphrase-multilingual-MiniLM-L12-v2` |

2. **Copiá tus PDF a la carpeta `data/`** (ver [`data/README.md`](data/README.md)).

## Ejecución

```bash
python main.py
# equivalente:
python -m asistente
```

Verás algo así (las cantidades dependen de tus PDF):

```
Cargando los documentos PDF...
Documentos cargados: 320 páginas
Fragmentos generados: 1450
PDFs cargados y retriever configurado.

🤖 Asistente iniciado. Escribí 'salir' para terminar.
Información general de carácter educativo. No reemplaza la consulta con un profesional de la salud.
--------------------------------------------------
👤 Vos:
```

Para terminar: escribí `salir` o `exit` (también funciona `Ctrl+C`).

## Cómo usar el agente

**Consultas sobre tus documentos** — cualquier pregunta que no sea una acción:

```
👤 Vos: ¿Qué dice el libro sobre la fibra dietaria?
🤖 Asistente: ...respuesta basada en los fragmentos recuperados...
```

Si la información no está en los PDF, debe responder:
*"Lo siento, no encuentro esa información en los documentos disponibles"*.

**Recordatorios por correo** — pedilos en lenguaje natural. Si falta algún dato, el bot
lo pregunta y **recuerda lo que ya le dijiste**:

```
👤 Vos: recordame tomar agua
🤖 Asistente: ¡Dale! Para dejarlo programado necesito unos datos más:
- ¿para qué día querés el recordatorio? (si querés una hora puntual, decímela; si no, lo mando a las 9:00)
- ¿cuántas veces querés que se repita? (por ejemplo: una sola vez, o 3 veces)
👤 Vos: mañana a las 8, 3 veces cada 2 días
🤖 Asistente: ✅ Recordatorio programado: "tomar agua"; te lo envío por correo 3 veces, una cada 2 día(s), desde el ...
```

- Frases que lo activan: *recordatorio, recordame, recuérdame, avisame, mandame un mail/correo…*
- Para abandonar un pedido a medias: `cancelar`, `olvidalo`, `dejalo` o `no quiero`.
- Hora por defecto: 09:00. Máximo de repeticiones: 30. Zona horaria: Argentina.
- ⚠️ Requiere el workflow de n8n **activado** y la URL de **producción** (`/webhook/...`),
  no la de prueba (`/webhook-test/...`).

**Turnos** — si el mensaje contiene `turno`, `agendar` o `reservar`, se envía a n8n.

**Prueba de Google Tasks** — escribí `prueban8n` para crear una tarea de prueba vía n8n.

## Pruebas

```bash
python -m unittest discover -s tests -t . -v
```

No necesitan internet, ni clave de Groq, ni PDF: simulan el LLM y n8n. Cubren el
estado de los recordatorios entre turnos, los errores de n8n y el orden de decisión del chat.

## Evaluación del retriever (Fase 4)

Para ver qué fragmentos recupera el sistema (con documento y página), sin gastar
llamadas al LLM ni necesitar clave de Groq:

```bash
python -m asistente.evaluacion "¿Qué es la fibra dietaria?"
```

Más detalle en [`docs/evaluacion.md`](docs/evaluacion.md).

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `No se encontró el PDF: ...` | Los PDF no están en `data/` o se llaman distinto. Copialos o ajustá `PDF_PATHS`. |
| `Falta instalar una dependencia (...)` | Falta `pip install -r requirements.txt` o no activaste el entorno virtual. |
| `ZoneInfoNotFoundError` (Windows) | Falta `tzdata`. Se instala con `requirements.txt`; si no: `pip install tzdata`. |
| Error de autenticación de Groq (401) | La clave es incorrecta o está vencida. Generá otra en console.groq.com. |
| Error 404 / "model not found" en Groq | Groq retiró el modelo. Cambiá `GROQ_MODEL` en `.env`. |
| `n8n no respondió` / `No se pudo conectar` | Revisá `N8N_WEBHOOK_URL`. Con la URL de prueba, n8n debe estar en *Listen for test event*. |
| El recordatorio da error en n8n | Usá la URL de **producción** con el workflow **activado**. |
| La primera ejecución tarda mucho | Está descargando el modelo de embeddings; las siguientes usan la caché. |

## Notas

- La base vectorial (Chroma) se arma **en memoria** en cada ejecución, igual que en el notebook:
  cada arranque vuelve a leer y vectorizar los PDF.
- Las versiones de las librerías **no están fijadas**, igual que en el notebook (`pip install -U`).
  Una vez que todo funcione en tu máquina, podés congelarlas con `pip freeze > requirements.lock.txt`.
- Contexto académico completo del proyecto: [`docs/descripcion_proyecto.md`](docs/descripcion_proyecto.md).
# iaii-agente-nutri
