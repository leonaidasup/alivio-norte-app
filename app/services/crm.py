"""CRM: aplicar una disposición mueve la etapa, deja audit trail y prepara el WhatsApp (sin enviarlo)."""
from app.data import database as store
from app.engine.drafts import ComplianceError, enforce_compliance


def _find_disposition(rules: dict, name):
    """Acepta mayúsculas y espacios de más: 'info  sent' vale como 'Info Sent'."""
    wanted = " ".join(str(name or "").split()).lower()
    for key, cfg in rules["disposiciones"].items():
        if key.lower() == wanted:
            return key, cfg
    return None, None


def _reject(c, lead_id, actor, kind, detail) -> dict:
    store.add_audit(c, lead_id, actor, "disposicion_rechazada", detail=detail)
    store.add_failure(c, lead_id, kind, detail)
    return {"ok": False, "status": "rechazada", "detail": detail}


def apply_disposition(database, rules: dict, lead_id: str, disposition: str, actor: str = "agente") -> dict:
    """Todo en una transacción: o queda la etapa, el audit y el WhatsApp, o no queda nada."""
    key, cfg = _find_disposition(rules, disposition)
    with database.tx() as c:
        lead = store.get_lead(c, lead_id)
        if lead is None:
            return _reject(c, lead_id, actor, "lead_desconocido", f"el lead '{lead_id}' no existe")
        if cfg is None:
            valid = ", ".join(rules["disposiciones"])
            return _reject(c, lead_id, actor, "disposicion_desconocida",
                           f"disposición desconocida: '{disposition}'. Válidas: {valid}")

        old, new = lead["stage"], cfg["etapa"]
        store.set_stage(c, lead_id, new)
        store.add_audit(c, lead_id, actor, "disposicion_aplicada", old, new, key)

        dnc_before = store.is_dnc(c, lead_id)
        if cfg.get("marcar_no_contactar"):
            store.mark_dnc(c, lead_id)

        outbox_id = None
        if dnc_before:   # quien pidió no ser contactado no recibe WhatsApp, aunque cambie de etapa
            store.add_audit(c, lead_id, actor, "whatsapp_omitido", detail="el lead pidió no ser contactado")
        else:
            try:
                template = cfg["whatsapp"].format(partner=rules["partner"],
                                                  consejero=rules["termino_personal_partner"])
                body = enforce_compliance(template, rules)
            except (ComplianceError, KeyError, IndexError, ValueError) as e:
                store.add_failure(c, lead_id, "whatsapp_no_generado", f"{key}: {e}")
            else:
                outbox_id = store.add_outbox(c, lead_id, lead["phone"], body, key)
        return {"ok": True, "status": "aplicada", "from": old, "to": new, "outbox_id": outbox_id}