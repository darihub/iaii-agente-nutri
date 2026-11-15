import json
from datetime import datetime
from zoneinfo import ZoneInfo
from langchain_core.messages import SystemMessage, HumanMessage

def detectar_intencion_tarea(pregunta,llm, historial):

    fecha_actual = datetime.now(
        ZoneInfo("America/Argentina/Buenos_Aires")
    ).isoformat()

    instrucciones = f"""
    Sos un asistente que identifica intenciones.

    Fecha actual: {fecha_actual}

    Analizá el mensaje del usuario.

    Si quiere crear una tarea en Google Tasks,
    devolvé un JSON con esta estructura:

    {{
        "accion": "crear_tarea",
        "titulo": "Título de la tarea",
        "notas": "Descripción opcional",
        "fecha_vencimiento": null
    }}

    Si el usuario indica una fecha, convertila a
    formato YYYY-MM-DD.

    Si no quiere crear una tarea, devolvé:

    {{
        "accion": "consulta"
    }}
    
    Tenés acceso al historial reciente de la conversación.
    Si el usuario pide guardar una respuesta anterior, como
    "guardá esa receta", usá el historial para recuperar su contenido.
    En ese caso:
    - El título debe describir la tarea.
    - El campo notas debe contener la receta completa,
      incluyendo ingredientes y preparación.
    - No inventes información que no esté en el historial.
    - Si no podés identificar la respuesta referida,
      no crees una tarea: devolvé accion "consulta".

    Respondé únicamente con JSON válido.
    No inventes fechas ni datos que no estén en el mensaje.
    """

    # Construir el contexto con los últimos 5 intercambios
    contexto = "\n\n".join(
        f"Usuario: {item['usuario']}\n"
        f"Asistente: {item['asistente']}"
        for item in historial[-5:]
    )

# Enviar el historial y la pregunta actual al LLM
    respuesta = llm.invoke([
        SystemMessage(content=instrucciones),
        HumanMessage(
            content=f"Historial:\n{contexto}\n\n"
                f"Mensaje actual: {pregunta}"
        )
    ])

    crudo = str(respuesta.content)
    m = re.search(r"\{.*\}", crudo, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {"accion": "consulta"}
    except json.JSONDecodeError:
        return {"accion": "consulta"}
