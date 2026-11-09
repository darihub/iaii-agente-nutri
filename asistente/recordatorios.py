# -*- coding: utf-8 -*-
"""RECORDATORIOS POR GMAIL (vía n8n).

Flujo: el usuario pide un recordatorio en lenguaje natural; el LLM extrae
fecha, mensaje y repeticiones. Si falta algo, el bot lo pregunta y conserva
lo ya informado hasta completar los datos. Luego envía la acción
"enviar_recordatorio" al webhook de n8n.

En el notebook el estado de la conversación en curso era una variable global
(`recordatorio_pendiente`). Acá vive dentro de `GestorRecordatorios.pendiente`;
la lógica es la misma.
"""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config
from .n8n_client import llamar_n8n

TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
HORA_POR_DEFECTO = "09:00"
MAX_REPETICIONES = 30
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

PATRON_RECORDATORIO = re.compile(
    r"recordatorio|record[aá]me|recordarme|recu[eé]rdame|recuerdame|"
    r"av[ií]same|avisarme|mand[aá]me un (mail|correo)|enviame un (mail|correo)",
    re.IGNORECASE,
)

PREGUNTAS_FALTANTES = {
    "fecha": "¿para qué día querés el recordatorio? (si querés una hora puntual, decímela; si no, lo mando a las 9:00)",
    "mensaje": "¿qué querés que te recuerde?",
    "repeticiones": "¿cuántas veces querés que se repita? (por ejemplo: una sola vez, o 3 veces)",
}


def detectar_intencion_recordatorio(texto):
    return bool(PATRON_RECORDATORIO.search(texto))


def _aplicar_datos(estado, nuevos):
    for clave in ("fecha", "hora", "mensaje", "repeticiones", "intervalo_dias"):
        valor = nuevos.get(clave)
        if valor in (None, "", "null"):
            continue
        if clave in ("repeticiones", "intervalo_dias"):
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                continue
        estado[clave] = valor


def _fecha_hora(estado):
    """Devuelve datetime con zona horaria o None si la fecha es inválida."""
    try:
        hora = estado.get("hora") or HORA_POR_DEFECTO
        return datetime.strptime(f"{estado['fecha']} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ_AR)
    except (KeyError, ValueError):
        return None


class GestorRecordatorios:
    """Maneja la conversación de un recordatorio a lo largo de varios turnos."""

    def __init__(self, llm):
        self.llm = llm
        # Estado del recordatorio en curso (None = no hay ninguno).
        self.pendiente = None

    def hay_pendiente(self):
        return self.pendiente is not None

    def extraer_datos(self, texto, estado):
        """Usa el LLM para extraer/actualizar los datos. Devuelve dict con claves
        fecha (YYYY-MM-DD), hora (HH:MM), mensaje, repeticiones, intervalo_dias."""
        ahora = datetime.now(TZ_AR)
        sistema = (
            "Extraés datos de un pedido de recordatorio por correo. "
            f"Hoy es {DIAS_ES[ahora.weekday()]} {ahora.strftime('%Y-%m-%d')} "
            "(zona horaria de Argentina). Respondé SOLO con un objeto JSON, sin texto extra, con las claves: "
            '"fecha" (YYYY-MM-DD o null), "hora" (HH:MM en 24 h o null), '
            '"mensaje" (qué hay que recordar, texto corto, o null), '
            '"repeticiones" (entero: cuántas veces se envía en total; "una sola vez" = 1; o null), '
            '"intervalo_dias" (entero: días entre envíos si el usuario lo indica, ej. "cada semana" = 7; o null). '
            "Resolvé fechas relativas (mañana, el viernes, en 3 días) a partir de la fecha de hoy. "
            "No inventes datos: si el usuario no lo dijo, usá null. "
            f"Datos ya conocidos de este pedido: {json.dumps(estado, ensure_ascii=False)}. "
            "Devolvé solo lo que el mensaje nuevo agrega o corrige; el resto en null."
        )
        try:
            resp = self.llm.invoke([("system", sistema), ("human", texto)])
            crudo = resp.content if isinstance(resp.content, str) else str(resp.content)
            m = re.search(r"\{.*\}", crudo, re.DOTALL)
            return json.loads(m.group(0)) if m else {}
        except Exception as e:
            print(f"⚠️ No pude interpretar el pedido ({e}).")
            return {}

    def responder(self, texto):
        """Maneja un turno de la conversación de recordatorio y devuelve la respuesta del bot."""
        if re.search(r"\b(cancel[aá]r?|olvidalo|dej[aá]lo|no quiero)\b", texto, re.IGNORECASE) \
                and self.pendiente is not None:
            self.pendiente = None
            return "Listo, cancelé el recordatorio. Si lo necesitás más tarde, pedímelo de nuevo."

        estado = self.pendiente if self.pendiente is not None else {}
        _aplicar_datos(estado, self.extraer_datos(texto, estado))
        self.pendiente = estado

        # Fecha en el pasado o inválida: se vuelve a preguntar.
        dt = _fecha_hora(estado) if estado.get("fecha") else None
        if estado.get("fecha") and (dt is None or dt <= datetime.now(TZ_AR)):
            estado.pop("fecha", None)
            estado.pop("hora", None)
            return "Esa fecha ya pasó o no pude entenderla. ¿Para qué día y hora querés el recordatorio?"

        faltantes = [c for c in ("fecha", "mensaje", "repeticiones") if c not in estado]
        if faltantes:
            pedidos = [PREGUNTAS_FALTANTES[c] for c in faltantes]
            if len(pedidos) == 1:
                return f"¡Dale! Para dejarlo programado, {pedidos[0]}"
            return "¡Dale! Para dejarlo programado necesito unos datos más:\n- " + "\n- ".join(pedidos)

        reps = max(1, min(int(estado["repeticiones"]), MAX_REPETICIONES))
        intervalo = max(1, int(estado.get("intervalo_dias") or 1))
        resultado = llamar_n8n("enviar_recordatorio", {
            "fecha": dt.isoformat(),
            "mensaje": estado["mensaje"],
            "repeticiones": reps,
            "intervalo_dias": intervalo,
            "email": config.EMAIL_DESTINO,
        })
        self.pendiente = None

        if resultado.get("success"):
            cuando = dt.strftime("%d/%m/%Y a las %H:%M")
            if reps == 1:
                detalle = f"te lo envío por correo el {cuando}."
            else:
                detalle = f"te lo envío por correo {reps} veces, una cada {intervalo} día(s), desde el {cuando}."
            return f"✅ Recordatorio programado: \"{estado['mensaje']}\"; {detalle}"
        return f"⚠️ No pude programar el recordatorio: {resultado.get('mensaje', 'error desconocido')}"
