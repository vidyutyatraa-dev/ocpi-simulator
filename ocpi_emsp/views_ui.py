import json
from django.shortcuts import render
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from .models import SimulatorConfig, CommandCallback, ChargingSession, ChargeDetailRecord, AuditLog
from .ocpi_utils import CPOClient, resolve_public_base_url

def dashboard_view(request: HttpRequest):
    """Renders the main simulator dashboard."""
    cfg = SimulatorConfig.get_config()
    public_url = resolve_public_base_url(request)
    recent_callbacks = CommandCallback.objects.all()[:15]
    recent_sessions = ChargingSession.objects.all()[:15]
    recent_cdrs = ChargeDetailRecord.objects.all()[:15]
    recent_logs = AuditLog.objects.all()[:20]

    context = {
        'config': cfg,
        'detected_public_url': public_url,
        'callbacks': recent_callbacks,
        'sessions': recent_sessions,
        'cdrs': recent_cdrs,
        'logs': recent_logs,
    }
    return render(request, 'ocpi_emsp/dashboard.html', context)

@csrf_exempt
def api_action_handshake(request: HttpRequest):
    """Trigger credentials handshake with CPO."""
    client = CPOClient(request)
    result = client.post_credentials()
    return JsonResponse(result)

@csrf_exempt
def api_action_locations(request: HttpRequest):
    """Fetch locations from CPO."""
    client = CPOClient(request)
    result = client.get_locations()
    return JsonResponse(result)

@csrf_exempt
def api_action_tariffs(request: HttpRequest):
    """Fetch tariffs from CPO."""
    client = CPOClient(request)
    result = client.get_tariffs()
    return JsonResponse(result)

@csrf_exempt
def api_action_put_token(request: HttpRequest):
    """Register RFID/App token with CPO."""
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    token_uid = body.get("token_uid", "RFID-TEST-001")
    valid = body.get("valid", True)
    client = CPOClient(request)
    result = client.put_token(token_uid, valid)
    return JsonResponse(result)

@csrf_exempt
def api_action_start_session(request: HttpRequest):
    """Dispatch START_SESSION command to CPO with resolved callback response_url."""
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    location_id = body.get("location_id", "VYKA001")
    evse_uid = body.get("evse_uid", "IN*VYT*EVYKA001")
    connector_id = int(body.get("connector_id", 1))
    token_uid = body.get("token_uid", "RFID-TEST-001")

    client = CPOClient(request)
    result = client.start_session(location_id, evse_uid, connector_id, token_uid)
    return JsonResponse({
        "result": result,
        "dispatched_response_url": f"{client.public_base}/ocpi/emsp/2.2.1/commands/callback"
    })

@csrf_exempt
def api_action_stop_session(request: HttpRequest):
    """Dispatch STOP_SESSION command to CPO."""
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    session_id = body.get("session_id", "").strip()
    if not session_id:
        return JsonResponse({"error": "session_id is required"}, status=400)

    client = CPOClient(request)
    result = client.stop_session(session_id)
    return JsonResponse({
        "result": result,
        "dispatched_response_url": f"{client.public_base}/ocpi/emsp/2.2.1/commands/callback"
    })

@csrf_exempt
def api_action_get_sessions(request: HttpRequest):
    """Trigger Get Sessions from CPO: GET /ocpi/cpo/2.2.1/sessions"""
    session_id = request.GET.get("session_id") or request.POST.get("session_id") or ""
    if not session_id and request.body:
        try:
            body = json.loads(request.body)
            session_id = body.get("session_id", "")
        except Exception:
            pass
    session_id = str(session_id).strip()
    client = CPOClient(request)
    result = client.get_sessions(session_id)
    
    # Sync retrieved sessions into local ChargingSession table
    data = result.get("data")
    items_to_sync = data if isinstance(data, list) else ([data] if isinstance(data, dict) and data else [])
    for s in items_to_sync:
        sid = s.get("id") or s.get("session_id")
        if sid:
            ChargingSession.objects.update_or_create(
                session_id=sid,
                defaults={
                    "country_code": s.get("country_code", "IN"),
                    "party_id": s.get("party_id", "VYT"),
                    "start_date_time": s.get("start_date_time", ""),
                    "end_date_time": s.get("end_date_time", ""),
                    "kwh": float(s.get("kwh", 0.0)),
                    "total_cost": float(s.get("total_cost", {}).get("excl_vat", 0.0) if isinstance(s.get("total_cost"), dict) else (s.get("total_cost") or 0.0)),
                    "currency": s.get("currency", "INR"),
                    "status": s.get("status", "ACTIVE"),
                    "raw_data": s
                }
            )
    return JsonResponse(result)

@csrf_exempt
def api_action_get_cdrs(request: HttpRequest):
    """Trigger Get CDRs from CPO: GET /ocpi/cpo/2.2.1/cdrs"""
    cdr_id = request.GET.get("cdr_id") or request.POST.get("cdr_id") or ""
    if not cdr_id and request.body:
        try:
            body = json.loads(request.body)
            cdr_id = body.get("cdr_id", "")
        except Exception:
            pass
    cdr_id = str(cdr_id).strip()
    client = CPOClient(request)
    result = client.get_cdrs(cdr_id)
    
    # Sync retrieved CDRs into local ChargeDetailRecord table
    data = result.get("data")
    items_to_sync = data if isinstance(data, list) else ([data] if isinstance(data, dict) and data else [])
    for c in items_to_sync:
        cid = c.get("id") or c.get("cdr_id")
        if cid:
            ChargeDetailRecord.objects.update_or_create(
                cdr_id=cid,
                defaults={
                    "session_id": c.get("session_id", ""),
                    "start_date_time": c.get("start_date_time", ""),
                    "end_date_time": c.get("end_date_time", ""),
                    "total_energy": float(c.get("total_energy", 0.0)),
                    "total_cost": float(c.get("total_cost", {}).get("excl_vat", 0.0) if isinstance(c.get("total_cost"), dict) else (c.get("total_cost") or 0.0)),
                    "currency": c.get("currency", "INR"),
                    "raw_data": c
                }
            )
    return JsonResponse(result)

@csrf_exempt
def api_action_update_config(request: HttpRequest):
    """Update simulator configuration."""
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}

    cfg = SimulatorConfig.get_config()
    if "cpo_url" in body:
        cfg.cpo_url = body["cpo_url"].strip()
    if "public_base_url" in body:
        cfg.public_base_url = body["public_base_url"].strip()
    if "token_b" in body:
        cfg.token_b = body["token_b"].strip()
    if "token_c" in body:
        cfg.token_c = body["token_c"].strip()
    if "token_a" in body:
        cfg.token_a = body["token_a"].strip()
    elif "bootstrap_token" in body:
        cfg.token_a = body["bootstrap_token"].strip()
    if "party_id" in body:
        cfg.party_id = body["party_id"].strip().upper()
    if "country_code" in body:
        cfg.country_code = body["country_code"].strip().upper()
    cfg.save()

    return JsonResponse({"status": "SUCCESS", "message": "Configuration saved"})

def api_get_callbacks(request: HttpRequest):
    """Polling API: Returns recent callbacks."""
    items = list(CommandCallback.objects.all().values('id', 'command_id', 'command_type', 'result', 'message', 'received_at')[:20])
    for item in items:
        if item.get('received_at'):
            item['received_at'] = item['received_at'].strftime('%H:%M:%S (%d %b)')
    return JsonResponse({"callbacks": items})

def api_get_sessions(request: HttpRequest):
    """Polling API: Returns active and historical sessions."""
    items = list(ChargingSession.objects.all().values('session_id', 'status', 'kwh', 'total_cost', 'currency', 'updated_at', 'raw_data')[:30])
    for item in items:
        if item.get('updated_at'):
            item['updated_at_fmt'] = item['updated_at'].strftime('%H:%M:%S (%d %b)')
    return JsonResponse({"sessions": items})

def api_get_cdrs(request: HttpRequest):
    """Polling API: Returns recent charge detail records."""
    items = list(ChargeDetailRecord.objects.all().values('cdr_id', 'session_id', 'total_energy', 'total_cost', 'currency', 'created_at', 'raw_data')[:30])
    for item in items:
        if item.get('created_at'):
            item['created_at_fmt'] = item['created_at'].strftime('%H:%M:%S (%d %b)')
    return JsonResponse({"cdrs": items})

def api_get_logs(request: HttpRequest):
    """Polling API: Returns recent audit logs with full JSON details."""
    items = list(AuditLog.objects.all().values('id', 'direction', 'module', 'endpoint', 'method', 'status_code', 'summary', 'details', 'timestamp')[:35])
    for item in items:
        if item.get('timestamp'):
            item['timestamp'] = item['timestamp'].strftime('%H:%M:%S')
    return JsonResponse({"logs": items})

@csrf_exempt
def api_clear_logs(request: HttpRequest):
    """Clears audit logs."""
    AuditLog.objects.all().delete()
    return JsonResponse({"status": "CLEARED"})


