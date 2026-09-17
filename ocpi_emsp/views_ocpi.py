import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import HttpRequest, JsonResponse
from .models import SimulatorConfig, CommandCallback, ChargingSession, ChargeDetailRecord
from .ocpi_utils import make_ocpi_response, resolve_public_base_url, log_ocpi_activity, utc_now_iso

logger = logging.getLogger('ocpi_emsp')

@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def ocpi_versions(request: HttpRequest) -> JsonResponse:
    """
    GET /ocpi/versions - OCPI version negotiation endpoint.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    base = resolve_public_base_url(request)
    log_ocpi_activity('IN', 'versions', request.path, 'GET', 200, 'Version list requested')
    return make_ocpi_response(
        data=[
            {
                "version": "2.2.1",
                "url": f"{base}/ocpi/emsp/2.2.1"
            }
        ]
    )

@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def ocpi_version_details(request: HttpRequest) -> JsonResponse:
    """
    GET /ocpi/emsp/2.2.1 - OCPI 2.2.1 Module endpoints catalog.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    base = resolve_public_base_url(request)
    endpoints = [
        {"identifier": "credentials", "role": "RECEIVER", "url": f"{base}/ocpi/emsp/2.2.1/credentials"},
        {"identifier": "commands", "role": "SENDER", "url": f"{base}/ocpi/emsp/2.2.1/commands"},
        {"identifier": "sessions", "role": "RECEIVER", "url": f"{base}/ocpi/emsp/2.2.1/sessions"},
        {"identifier": "cdrs", "role": "RECEIVER", "url": f"{base}/ocpi/emsp/2.2.1/cdrs"},
    ]
    log_ocpi_activity('IN', 'versions', request.path, 'GET', 200, 'Endpoint details requested')
    return make_ocpi_response(
        data={
            "version": "2.2.1",
            "endpoints": endpoints
        }
    )

@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "OPTIONS"])
def ocpi_credentials(request: HttpRequest) -> JsonResponse:
    """
    POST/GET /ocpi/emsp/2.2.1/credentials - Handshake endpoint.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    cfg = SimulatorConfig.get_config()
    base = resolve_public_base_url(request)

    if request.method in ["POST", "PUT"]:
        try:
            body = json.loads(request.body or "{}")
        except Exception:
            body = {}

        # CPO provides its token (which we will use as Token B when calling CPO)
        new_token_b = body.get("token")
        if new_token_b:
            cfg.token_b = new_token_b
            cfg.save()
            logger.info(f"Updated Token B from CPO credentials payload: {new_token_b[:6]}...")

        # CPO provides its base URL
        cpo_base_url = body.get("url")
        if cpo_base_url:
            cfg.cpo_url = cpo_base_url
            cfg.save()

        log_ocpi_activity('IN', 'credentials', request.path, request.method, 200, 'CPO completed credentials handshake', {'received': body})

    # Return EMSP credentials to CPO
    data = {
        "token": cfg.token_c,
        "url": f"{base}/ocpi/emsp/2.2.1",
        "roles": [
            {
                "role": "EMSP",
                "party_id": cfg.party_id,
                "country_code": cfg.country_code,
                "business_details": {
                    "name": "VidyutYatraa EMSP Simulator",
                    "website": "https://vidyutyatraa.co.in"
                }
            }
        ]
    }
    return make_ocpi_response(data=data)

@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def ocpi_command_callback(request: HttpRequest, command_id: str = "") -> JsonResponse:
    """
    POST /ocpi/emsp/2.2.1/commands/callback
    CRITICAL: Receives asynchronous CommandResult callback from vidyutYatraaOCPICommands Lambda.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    result_status = payload.get("result", "UNKNOWN")
    messages = payload.get("message", [])
    msg_text = messages[0].get("text", "") if messages and isinstance(messages, list) else str(messages)
    session_id = payload.get("session_id", "")

    # Determine command type if known
    cmd_type = "START_SESSION" if "start" in msg_text.lower() else ("STOP_SESSION" if "stop" in msg_text.lower() else "GENERIC")

    # Persist callback to database
    record = CommandCallback.objects.create(
        command_id=command_id or payload.get("command_id", ""),
        command_type=cmd_type,
        result=result_status,
        message=msg_text,
        payload=payload
    )

    # Format summary with session_id for Activity & Audit Log visibility
    if session_id:
        summary = f"Callback [{session_id}]: {result_status} ({msg_text})"
    else:
        summary = f"Callback received: {result_status} ({msg_text})"

    logger.info(f"SUCCESS: Received CPO CommandResult callback: result={result_status}, session_id={session_id}, msg={msg_text}")
    log_ocpi_activity('IN', 'commands', request.path, 'POST', 200, summary, {
        'session_id': session_id,
        'result': result_status,
        'command_type': cmd_type,
        'message': msg_text,
        'payload': payload
    })

    return make_ocpi_response(
        data={"received": True, "id": record.id},
        status_message="Callback processed successfully"
    )

@csrf_exempt
@require_http_methods(["GET", "PUT", "PATCH", "OPTIONS"])
def ocpi_session_receiver(request: HttpRequest, country_code: str = "IN", party_id: str = "VYT", session_id: str = "") -> JsonResponse:
    """
    PUT /sessions/:cc/:party/:id - Receive session when charger starts.
    PATCH /sessions/:cc/:party/:id - Receive telemetry / status updates.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        payload = {}

    if request.method in ["PUT", "PATCH"]:
        session, _ = ChargingSession.objects.get_or_create(session_id=session_id)
        session.country_code = country_code
        session.party_id = party_id
        if "start_date_time" in payload:
            session.start_date_time = payload["start_date_time"]
        if "end_date_time" in payload:
            session.end_date_time = payload["end_date_time"]
        if "kwh" in payload:
            session.kwh = float(payload["kwh"])
        if "total_cost" in payload:
            session.total_cost = float(payload.get("total_cost", {}).get("excl_vat", 0.0) if isinstance(payload.get("total_cost"), dict) else payload.get("total_cost", 0.0))
        if "status" in payload:
            session.status = payload["status"]
        session.raw_data = payload
        session.save()

        log_ocpi_activity('IN', 'sessions', request.path, request.method, 200, f"Session Push [{session_id}]: {session.status} ({session.kwh} kWh)", {
            'session_id': session_id,
            'status': session.status,
            'kwh': session.kwh,
            'total_cost': session.total_cost,
            'payload': payload
        })
        return make_ocpi_response(data={"session_id": session_id})

    # GET
    try:
        session = ChargingSession.objects.get(session_id=session_id)
        return make_ocpi_response(data=session.raw_data)
    except ChargingSession.DoesNotExist:
        return make_ocpi_response(status_code=2003, status_message="Session not found", http_status=404)

@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def ocpi_cdr_receiver(request: HttpRequest, cdr_id: str = "") -> JsonResponse:
    """
    POST /ocpi/emsp/2.2.1/cdrs - Receive completed Charge Detail Record.
    """
    if request.method == "OPTIONS":
        return make_ocpi_response({})

    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except Exception:
            payload = {}

        cid = payload.get("id") or payload.get("cdr_id") or cdr_id or "UNKNOWN"
        cdr, _ = ChargeDetailRecord.objects.get_or_create(cdr_id=cid)
        cdr.session_id = payload.get("session_id", "")
        cdr.start_date_time = payload.get("start_date_time", "")
        cdr.end_date_time = payload.get("end_date_time", "")
        cdr.total_energy = float(payload.get("total_energy", 0.0))
        cdr.total_cost = float(payload.get("total_cost", {}).get("excl_vat", 0.0) if isinstance(payload.get("total_cost"), dict) else payload.get("total_cost", 0.0))
        cdr.currency = payload.get("currency", "INR")
        cdr.raw_data = payload
        cdr.save()

        log_ocpi_activity('IN', 'cdrs', request.path, 'POST', 200, f"CDR Push [{cid}] Session [{cdr.session_id}]: {cdr.total_energy} kWh", {
            'cdr_id': cid,
            'session_id': cdr.session_id,
            'total_energy': cdr.total_energy,
            'total_cost': cdr.total_cost,
            'payload': payload
        })
        return make_ocpi_response(data={"cdr_id": cid}, http_status=201)

    # GET
    if cdr_id:
        try:
            cdr = ChargeDetailRecord.objects.get(cdr_id=cdr_id)
            return make_ocpi_response(data=cdr.raw_data)
        except ChargeDetailRecord.DoesNotExist:
            return make_ocpi_response(status_code=2003, status_message="CDR not found", http_status=404)

    cdrs = list(ChargeDetailRecord.objects.all().values('cdr_id', 'total_energy', 'total_cost', 'currency', 'created_at')[:50])
    return make_ocpi_response(data=cdrs)

