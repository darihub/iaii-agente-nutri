🚀 Proyecto Integrador: Asistente Virtual Inteligente con LLMs, RAG y n8n

📌 ¿De qué trata el proyecto?

El objetivo de este proyecto es construir desde cero un Agente Conversacional
(Chatbot) de nivel empresarial. A diferencia de los bots antiguos que respondían
con menús de opciones fijas, este asistente utilizará Inteligencia Artificial
Generativa (LLMs) para entender el lenguaje natural, razonar, consultar
documentos privados de una empresa y ejecutar acciones automatizadas en el mundo
real.

El proyecto se divide en 4 grandes fases, simulando un entorno de trabajo real
de Ingeniería de Software e IA:

🧠 FASE 1: Concepción y Diseño (Semanas 1 a 4)

Objetivo: Definir qué problema va a resolver el bot y darle una "personalidad".

1.  Definición del Caso de Uso: Los equipos elegirán un dominio. Por ejemplo: un
    asistente para alumnos de la UAA que responda dudas sobre correlativas, o un
    bot de atención al cliente para una clínica médica.
2.  Prompt Engineering: En lugar de programar reglas lógicas (IF/THEN), los
    alumnos diseñarán el System Prompt (las instrucciones base del modelo). Aquí
    definirán el tono del bot, sus límites (qué no debe responder) y su formato
    de salida.
3.  Selección del Modelo: Decidirán si usarán un modelo a través de una API
    (como OpenAI/ChatGPT) o un modelo de código abierto (como Llama 3)
    descargado desde Hugging Face.

📚 FASE 2: Memoria y Conocimiento Privado (Semanas 4 a 8)

Objetivo: Evitar que el modelo "alucine" (invente respuestas) dándole acceso a
documentos reales mediante la técnica RAG (Retrieval-Augmented Generation).

1.  Recopilación de Datos: Los alumnos juntarán PDFs, reglamentos o manuales de
    la empresa elegida.
2.  Vectorización (Embeddings): Usando lo aprendido en la Clase 11,
    transformarán esos textos en vectores matemáticos (Embeddings) y los
    guardarán en una Base de Datos Vectorial (ej. ChromaDB).
3.  Orquestación con LangChain: Programarán un script en Python usando el
    framework LangChain. El flujo será:
      - El usuario hace una pregunta.
      - El sistema busca en la base de datos vectorial los párrafos más
        relevantes.
      - El sistema le envía al LLM la pregunta del usuario + los párrafos
        encontrados.
      - El LLM lee la información y redacta una respuesta perfecta y
        fundamentada.

⚙️ FASE 3: Acción y Automatización (Semanas 9 a 12)

Objetivo: Darle "manos" al chatbot para que no solo hable, sino que ejecute
tareas usando n8n (una herramienta de automatización de flujos de trabajo).

1.  Conexión de APIs: Los alumnos conectarán su código Python con n8n mediante
    Webhooks.
2.  Ejecución de Tareas: Si el usuario le dice al bot "Quiero reservar un turno
    para mañana", el LLM extraerá la intención y la fecha, y enviará una señal a
    n8n.
3.  Flujo en n8n: n8n recibirá la señal, se conectará automáticamente a Google
    Calendar para agendar el turno, y enviará un correo electrónico de
    confirmación al usuario. ¡El bot ahora interactúa con el mundo real!

📊 FASE 4: Evaluación, Optimización y Despliegue (Semanas 12 a 16)

Objetivo: Aplicar el rigor de la ingeniería para medir la calidad del sistema.

1.  Métricas de Calidad: Los alumnos no pueden simplemente decir "el bot
    responde bien". Deberán medir la Precision y el Recall de su sistema de
    búsqueda de documentos (¿Está recuperando los párrafos correctos de la base
    de datos?).
2.  Ajuste Fino: Modificarán los hiperparámetros (tamaño de los chunks de texto,
    temperatura del LLM) para optimizar el rendimiento.
3.  Presentación Final: Documentarán la arquitectura del sistema y presentarán  un informe con el desarrollo del proyecto.
