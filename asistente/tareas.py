import json
from datetime import datetime
from zoneinfo import ZoneInfo
from langchain_core.messages import SystemMessage, HumanMessage

def detectar_intencion_tarea(pregunta,llm):

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

    Respondé únicamente con JSON válido.
    No inventes fechas ni datos que no estén en el mensaje.
    """

    respuesta = llm.invoke([
        SystemMessage(content=instrucciones),
        HumanMessage(content=pregunta)
    ])

    return json.loads(respuesta.content)
