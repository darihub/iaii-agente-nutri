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

    return json.loads(respuesta.content)
