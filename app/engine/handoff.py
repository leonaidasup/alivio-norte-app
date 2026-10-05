"""Resumen para el agente humano cuando el caso se escala."""

ACTIONS = {
    "riesgo_emocional": "PRIORIDAD MÁXIMA. Contactar cuanto antes con una persona real; no usar plantillas.",
    "legal": "No dar opinión legal. Que un Consejero revise el caso.",
    "datos_sensibles": "Compartió datos sensibles (ya redactados). No repetirlos y pedir que no los envíe por chat.",
    "hostigamiento_cobranza": "Reporta acoso de cobranza. Responder con calma y escuchar antes de ofrecer algo.",
    "fraude_o_desconfianza": "Desconfía o menciona fraude. Explicar el proceso con calma, sin presionar.",
    "promesa_de_ahorro": "Pregunta por ahorro o garantías. No prometer: depende del perfil.",
    "precio_o_tarifas": "Pregunta por costos. No inventar tarifas; que las explique el Consejero.",
    "deuda_ajena_o_disputada": "Dice que la deuda no es suya o la disputa. No pre-calificar; revisar el caso.",
    "deuda_no_elegible": "Su deuda no es elegible para el programa. Revisar alternativas.",
    "monto_alto": "Monto alto: revisión manual antes de pre-calificar.",
    "mensaje_ambiguo": "No se entiende de qué trata. Leer el mensaje y pedir aclaración.",
    "no_contactar_previo": "Esta persona pidió no ser contactada. No enviar nada sin revisar.",
    "error_procesamiento": "El sistema falló al procesar el mensaje. Revisarlo a mano.",
}
DEFAULT_ACTION = "Revisar el mensaje y responder manualmente."


def build_summary(d, lead_id: str, text: str, creator: str = "", channel: str = "") -> str:
    """Texto corto: qué pasó, por qué se escaló y qué hacer. El texto ya viene redactado."""
    extract = " ".join(text.split())[:240]
    lines = [
        f"Lead: {lead_id}" + (f" | Creador: {creator}" if creator else "") + (f" | Canal: {channel}" if channel else ""),
        f"Motivo: {d.reason}",
        f"Por qué: {d.explanation}",
        f"Mensaje: \"{extract}\"",
    ]
    datos = []
    if d.amount and d.amount.total:
        datos.append(f"monto {d.amount.total:,} USD")
    if d.debt_types.get("eligible"):
        datos.append("deuda elegible: " + ", ".join(d.debt_types["eligible"]))
    if d.debt_types.get("ineligible"):
        datos.append("deuda NO elegible: " + ", ".join(d.debt_types["ineligible"]))
    if d.wants_counselor:
        datos.append("pide hablar con un Consejero")
    if d.urgent:
        datos.append("marcó urgencia")
    if datos:
        lines.append("Datos: " + "; ".join(datos))
    lines.append("Qué hacer: " + ACTIONS.get(d.reason, DEFAULT_ACTION))
    return "\n".join(lines)