# Asistente nutricional con RAG, Groq y n8n

Aplicación de línea de comandos para responder consultas nutricionales usando documentos PDF como contexto, programar recordatorios por correo y generar/guardar recetas y tareas a través de n8n.

El proyecto combina:

- RAG sobre PDFs con Chroma + embeddings
- LLM de Groq para responder y extraer información
- flujo de recordatorios por email vía n8n
- generación y carga de recetas en Google Sheets
- creación de tareas en Google Tasks

> ⚠️ El asistente es informativo y educativo. No reemplaza la atención profesional de un nutricionista o médico.
> Para ver los límites del sistema, consultá [`docs/limites_seguridad.md`](docs/limites_seguridad.md).

---

## Características principales

1. Búsqueda contextual sobre documentos
   - Lee PDFs desde `data/`
   - Fragmenta y vectoriza los textos con embeddings
   - Recupera los fragmentos más relevantes para cada pregunta
   - Responde usando únicamente ese contexto

2. Recordatorios por correo
   - Detecta frases como “recordame tomar agua mañana a las 8”
   - Recolecta los datos faltantes en conversación
   - Envía la acción final a un webhook de n8n

3. Generación de recetas
   - Identifica pedidos con palabras como “receta”, “excel”, “planilla”, etc.
   - Usa RAG para obtener contexto nutricional relevante
   - Genera recetas en JSON y las envía a n8n para cargarlas en el Sheet del usuario

4. Tareas en Google Tasks
   - Detecta intención de crear tareas
   - Las envía al webhook de n8n

---

## Requisitos

- Python 3.10 o superior
- Cuenta y API key de Groq: <https://console.groq.com>
- PDF de referencia en la carpeta `data/`
- (Opcional) workflow de n8n activo para recordatorios, recetas y tasks
- Conexión a internet para acceder a Groq y descargar modelos embeddings iniciales

---

## Estructura del proyecto

```text
asistente-nutricional-rag/
├── .env.example              # plantilla de variables de entorno
├── .gitignore
├── README.md
├── main.py                   # entrada principal: python main.py
├── requirements.txt          # dependencias del proyecto
├── asistente/
│   ├── __init__.py
│   ├── __main__.py           # permite ejecutar: python -m asistente
│   ├── app.py                # inicialización del sistema
│   ├── chat.py               # bucle principal del chat
│   ├── config.py             # configuración, .env y defaults
│   ├── evaluacion.py         # análisis de recuperación del retriever
│   ├── llm.py                # creación del LLM y cadena RAG
│   ├── n8n_client.py         # integración con n8n
│   ├── prompts.py            # prompts y aviso permanente
│   ├── rag.py                # lectura, chunking y vectorstore
│   ├── recetas.py            # generación y envío de recetas
│   ├── recordatorios.py      # lógica de recordatorios
│   ├── tareas.py             # detección de intención de tareas
│   └── ...
├── data/                     # PDF del proyecto (no se sube a GitHub)
├── docs/
│   ├── contrato_n8n.md
│   ├── descripcion_proyecto.md
│   ├── evaluacion.md
│   ├── limites_seguridad.md
│   └── n8n_recetas_por_usuario.md
├── tests/
│   └── ...
└── chroma_db/                # base vectorial local generada al correr el proyecto
```

---

## Instalación

```bash
git clone <URL-del-repositorio>
cd asistente-nutricional-rag

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# o Windows cmd
# .\.venv\Scripts\activate.bat

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

---

## Configuración

1. Copiá `.env.example` a `.env`.

```bash
copy .env.example .env
# o en Unix/macOS: cp .env.example .env
```

2. Completa las variables relevantes:

```env
GROQ_API_KEY=
N8N_WEBHOOK_URL=https://tu-instancia.app.n8n.cloud/webhook/tu-path
EMAIL_DESTINO=
PDF_PATHS=data/LIBRO1.pdf,data/LIBRO2.pdf
GROQ_MODEL=openai/gpt-oss-20b
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
USUARIO=
```

### Variables importantes

- `GROQ_API_KEY`: clave de Groq. Si no está definida, la app la pedirá por consola.
- `N8N_WEBHOOK_URL`: URL del webhook de n8n para recordatorios/tareas/recetas.
- `EMAIL_DESTINO`: correo por defecto para los recordatorios.
- `PDF_PATHS`: lista de PDFs separados por coma; rutas relativas se resuelven desde la raíz del proyecto.
- `USUARIO`: alias o correo para identificar el usuario del Excel de recetas. Si no se define, se usa `EMAIL_DESTINO` y luego se pregunta al iniciar.
- `GROQ_MODEL`: modelo LLM a usar con Groq.
- `EMBEDDING_MODEL`: modelo de embeddings para la base vectorial.

El archivo [`asistente/config.py`](asistente/config.py) centraliza estos valores y además:

- carga `.env` automáticamente
- resuelve PDFs relativos desde la raíz del proyecto
- valida y normaliza el usuario
- pide la API key si faltara

---

## Ejecución

```bash
python main.py
```

También podés correrlo como módulo:

```bash
python -m asistente
```

Al iniciar, el sistema:

1. solicita la API key de Groq si es necesario
2. obtiene el usuario para el Excel de recetas
3. carga los PDFs y arma el retriever/vectorstore
4. crea el LLM y la cadena RAG
5. entra al bucle de chat

Para salir del chat, escribí `salir` o `exit`.

---

## Uso del asistente

### Consultas sobre documentos

Ejemplo:

```text
👤 Vos: ¿Qué dice el libro sobre la fibra dietaria?
🤖 Asistente: ...respuesta basada en los fragmentos recuperados...
```

Si la información no aparece en los PDFs, el sistema responde indicando que no encontró ese dato en los documentos disponibles.

### Recordatorios por correo

Ejemplo:

```text
👤 Vos: recordame tomar agua mañana a las 8, 3 veces
🤖 Asistente: ¡Dale! Para dejarlo programado necesito unos datos más:
- ¿para qué día querés el recordatorio?
- ¿cuántas veces querés que se repita?

👤 Vos: mañana a las 8, 3 veces cada 2 días
🤖 Asistente: ✅ Recordatorio programado: "tomar agua"; te lo envío por correo 3 veces, una cada 2 día(s), desde el ...
```

Se aceptan frases como:

- recordatorio
- recordame
- recuérdame
- avisame
- mandame un mail / correo

También se puede cancelar con frases como `cancelar`, `olvidalo`, `dejalo` o `no quiero`.

### Recetas

Ejemplo:

```text
👤 Vos: armame 2 recetas altas en proteína para guardar en el excel
🤖 Asistente: ✅ Recetas cargadas en el Sheet: ...
```

Esto genera recetas tomando contexto de los PDFs y las envía a n8n para agregarlas en una hoja de Google Sheets asociada al usuario.

### Tareas en Google Tasks

El asistente puede detectar pedidos de creación de tareas y delegarlos a n8n para registrar tareas en Google Tasks.

---

## Validación y pruebas

```bash
python -m unittest discover -s tests -t . -v
```

Las pruebas cubren:

- manejo del estado de recordatorios entre turnos
- errores de integración con n8n
- decisión del orden del chat y rutinas de control
- validación de flujos sin depender de internet ni clave de Groq

---

## Evaluación del retriever

Para inspeccionar qué fragmentos devuelve el sistema, sin gastar llamadas a Groq:

```bash
python -m asistente.evaluacion "¿Qué es la fibra dietaria?"
```

Más detalle en [`docs/evaluacion.md`](docs/evaluacion.md).

---

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `No se encontró el PDF` | Los archivos no están en `data/` o el nombre no coincide con `PDF_PATHS`. |
| `Falta instalar una dependencia` | Ejecutá `pip install -r requirements.txt` y revisá que el entorno virtual esté activado. |
| `ZoneInfoNotFoundError` (Windows) | Instalá `tzdata` con `pip install tzdata`. |
| Error 401 de Groq | La API key está vencida, incorrecta o no existe. |
| Error 404 / model not found | El modelo de Groq fue removido o cambió de nombre. Revisá `GROQ_MODEL`. |
| `n8n no respondió` | Verificá `N8N_WEBHOOK_URL` y que el workflow esté activo. |
| El recordatorio falla en n8n | Usá la URL de producción (`/webhook/...`) y no la URL de prueba (`/webhook-test/...`). |
| Primera ejecución muy lenta | El sistema está descargando el modelo de embeddings; luego queda cacheado. |

---

## Documentación relacionada

- [`docs/descripcion_proyecto.md`](docs/descripcion_proyecto.md)
- [`docs/contrato_n8n.md`](docs/contrato_n8n.md)
- [`docs/limites_seguridad.md`](docs/limites_seguridad.md)
- [`docs/evaluacion.md`](docs/evaluacion.md)

---

## Notas

- La base vectorial se construye en cada ejecución y se almacena localmente en `chroma_db/`.
- El proyecto usa dependencias sin fijar versión exacta, como en el notebook original; si querés, podés congelarlas con `pip freeze > requirements.lock.txt`.
- La lógica principal del sistema está centralizada en `asistente/config.py`, `asistente/rag.py`, `asistente/llm.py`, `asistente/chat.py` y la integración con n8n en `asistente/n8n_client.py`.
