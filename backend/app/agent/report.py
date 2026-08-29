"""Construccion determinista del reporte operacional del contrato."""
import time
import uuid


def _problem_code(problem):
    text = (problem or "").lower()
    if any(word in text for word in ("cansad", "dormid", "fatig")):
        return "worker_fatigue"
    if any(word in text for word in ("accidente", "choque", "emergencia")):
        return "safety_incident"
    if any(word in text for word in ("camion", "vehiculo", "motor", "rueda", "averia")):
        return "vehicle_issue"
    return "unknown" if problem else "normal"


def build(event, call, outcome=None, voice=None, status="done", transcript=""):
    payload = event.get("payload", {})
    outcome = outcome or {}
    voice = voice or {}
    needs_human = bool(outcome.get("needs_human")) or status != "done"
    problem = outcome.get("problem")
    code = "no_contact" if status in ("no_answer", "busy") else _problem_code(problem)
    risk = float(voice.get("risk", 0) or 0)

    if status in ("no_answer", "busy"):
        level, reason = "high", "No se pudo contactar al trabajador"
    elif code == "safety_incident":
        level, reason = "critical", problem or "Posible incidente de seguridad"
    elif code == "worker_fatigue" or risk >= 0.6 or needs_human:
        level, reason = "high", problem or "Se requiere intervencion humana"
    elif event.get("type") == "truck.slowdown":
        level, reason = "medium", "Caida abrupta de velocidad"
    else:
        level, reason = "low", "Confirmacion operacional"

    if needs_human and level == "low":
        level = "high"
        reason = "Informacion insuficiente; requiere revision humana"

    if status == "done" and not needs_human:
        resolution = "La llamada termino y se registro la respuesta del trabajador"
    elif status == "done":
        resolution = "Se registro la respuesta y se escalo el caso a operaciones"
    else:
        resolution = "No hubo una conclusion automatica; se escalo el caso a operaciones"

    if level in ("high", "critical"):
        steps = [{"action": "Contactar al supervisor de turno", "owner": "operations", "status": "pending"}]
    elif outcome.get("available") is False:
        steps = [{"action": "Confirmar nueva disponibilidad", "owner": "worker", "status": "pending"}]
    else:
        steps = [{"action": "Continuar seguimiento de la operacion", "owner": "operations", "status": "pending"}]

    summary = problem or ("Sin respuesta del trabajador" if status != "done" else "Respuesta operacional sin incidente informado")
    return {
        "id": f"report_{uuid.uuid4().hex[:16]}",
        "operation_id": payload.get("trip_id", "unknown"),
        "worker_id": payload.get("worker_id", "unknown"),
        "call_id": call["call_id"],
        "event_type": event.get("type", "truck.stopped"),
        "what_happened": payload.get("detail") or event.get("type", "evento operacional"),
        "where": {"lat": payload.get("lat", 0), "lon": payload.get("lon", 0),
                  "label": payload.get("location_label", "Ubicacion no disponible")},
        "triage": {"level": level, "needs_human": needs_human, "reason": reason},
        "agent_resolution": resolution,
        "next_steps": steps,
        "diagnosis": {"code": code, "summary": summary, "confidence": 0.0 if code in ("unknown", "no_contact") else 0.75},
        "worker_feedback": {"summary": summary, "available": outcome.get("available"),
                             "eta_min": outcome.get("eta_min")},
        "call_status": status,
        "transcript": transcript or "",
        "created_at": time.time(),
    }
