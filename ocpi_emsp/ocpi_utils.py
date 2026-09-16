import os
import json
import logging
import requests
from datetime import datetime, timezone
from django.http import JsonResponse
from django.utils import timezone as dj_timezone

logger = logging.getLogger('ocpi_emsp')

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def resolve_public_base_url(request=None) -> str:
    """
    Deterministically resolves the external routable base URL for callbacks.
    GUARANTEE: Will never return '0.0.0.0', preventing unroutable callback delivery.
    """
    # 1. Environment variable override
    env_url = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if env_url and not "0.0.0.0" in env_url:
        return env_url.rstrip("/")

    # 2. Database configuration
    try:
        from .models import SimulatorConfig
        cfg = SimulatorConfig.get_config()
        if cfg.public_base_url and not "0.0.0.0" in cfg.public_base_url:
            return cfg.public_base_url.strip().rstrip("/")
    except Exception:
        pass

    # 3. Dynamic HTTP Request header inspection
    if request:
        host = request.get_host()
        if host and not host.startswith("0.0.0.0"):
            scheme = "https" if request.is_secure() else "http"
            return f"{scheme}://{host}".rstrip("/")

    # 4. Fallback safe default (localhost)
    return "http://localhost:8000"

def make_ocpi_response(data=None, status_code: int = 1000, status_message: str = "Success", http_status: int = 200) -> JsonResponse:
    """
    Constructs an HTTP response matching standard OCPI 2.2.1 envelope format.
    """
    payload = {
        "status_code": status_code,
        "status_message": status_message,
        "timestamp": utc_now_iso(),
        "data": data if data is not None else {}
    }
    return JsonResponse(payload, status=http_status, json_dumps_params={'indent': 2})

def log_ocpi_activity(direction: str, module: str, endpoint: str, method: str = 'POST', status_code: int = 200, summary: str = '', details: dict = None):
    """
    Saves an audit record to the SQLite database.
    """
    try:
        from .models import AuditLog
        AuditLog.objects.create(
            direction=direction,
            module=module,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            summary=summary,
            details=details or {}
        )
    except Exception as e:
        logger.warning(f"Failed to record audit log: {e}")

class CPOClient:
    """
    Client for dispatching OCPI requests from this EMSP simulator to VidyutYatraa CPO.
    """
    def __init__(self, request=None):
        from .models import SimulatorConfig
        self.config = SimulatorConfig.get_config()
        self.request = request
        self.public_base = resolve_public_base_url(request)

    @property
    def headers(self):
        token = self.config.token_b
        return {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }

    @property
    def bootstrap_headers(self):
        token = self.config.bootstrap_token or self.config.token_b
        return {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }

    def post_credentials(self) -> dict:
        """Handshake: POST /ocpi/cpo/2.2.1/credentials"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/credentials"
        payload = {
            "token": self.config.token_c,
            "url": f"{self.public_base}/ocpi/emsp/2.2.1",
            "roles": [
                {
                    "role": "EMSP",
                    "party_id": self.config.party_id,
                    "country_code": self.config.country_code,
                    "business_details": {
                        "name": "VidyutYatraa EMSP Simulator",
                        "website": "https://vidyutyatraa.co.in"
                    }
                }
            ]
        }
        try:
            res = requests.post(url, json=payload, headers=self.bootstrap_headers, timeout=12)
            log_ocpi_activity('OUT', 'credentials', url, 'POST', res.status_code, 'Credentials Handshake', {'request': payload, 'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            log_ocpi_activity('OUT', 'credentials', url, 'POST', 0, f'Credentials failed: {e}')
            return {"error": str(e)}

    def get_locations(self) -> dict:
        """Fetch stations: GET /ocpi/cpo/2.2.1/locations"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/locations"
        try:
            res = requests.get(url, headers=self.headers, timeout=12)
            log_ocpi_activity('OUT', 'locations', url, 'GET', res.status_code, 'Fetch Locations', {'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            return {"error": str(e)}

    def get_tariffs(self) -> dict:
        """Fetch tariffs: GET /ocpi/cpo/2.2.1/tariffs"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/tariffs"
        try:
            res = requests.get(url, headers=self.headers, timeout=12)
            log_ocpi_activity('OUT', 'tariffs', url, 'GET', res.status_code, 'Fetch Tariffs', {'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            return {"error": str(e)}

    def put_token(self, token_uid: str = "RFID-TEST-001", valid: bool = True) -> dict:
        """Register RFID Token: PUT /ocpi/cpo/2.2.1/tokens/:cc/:party/:uid"""
        cc = self.config.country_code
        party = self.config.party_id
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/tokens/{cc}/{party}/{token_uid}"
        payload = {
            "country_code": cc,
            "party_id": party,
            "uid": token_uid,
            "type": "RFID",
            "contract_id": token_uid,
            "issuer": "VY-Simulator",
            "auth_id": token_uid,
            "valid": valid,
            "whitelist": "ALLOWED",
            "last_updated": utc_now_iso()
        }
        try:
            res = requests.put(url, json=payload, headers=self.headers, timeout=12)
            log_ocpi_activity('OUT', 'tokens', url, 'PUT', res.status_code, f'Register Token {token_uid}', {'payload': payload, 'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            return {"error": str(e)}

    def start_session(self, location_id: str, evse_uid: str, connector_id: int, token_uid: str) -> dict:
        """Trigger Start Session: POST /ocpi/cpo/2.2.1/commands/START_SESSION"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/commands/START_SESSION"
        response_url = f"{self.public_base}/ocpi/emsp/2.2.1/commands/callback"
        payload = {
            "response_url": response_url,
            "token": {
                "country_code": self.config.country_code,
                "party_id": self.config.party_id,
                "uid": token_uid,
                "type": "RFID",
                "contract_id": token_uid,
                "issuer": "VY-Simulator",
                "auth_id": token_uid,
                "valid": True,
                "whitelist": "ALLOWED"
            },
            "location_id": location_id,
            "evse_uid": evse_uid,
            "connector_id": str(connector_id)
        }
        try:
            res = requests.post(url, json=payload, headers=self.headers, timeout=15)
            log_ocpi_activity('OUT', 'commands', url, 'POST', res.status_code, f'START_SESSION -> callback: {response_url}', {'payload': payload, 'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            log_ocpi_activity('OUT', 'commands', url, 'POST', 0, f'START_SESSION failed: {e}')
            return {"error": str(e)}

    def stop_session(self, session_id: str) -> dict:
        """Trigger Stop Session: POST /ocpi/cpo/2.2.1/commands/STOP_SESSION"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/commands/STOP_SESSION"
        response_url = f"{self.public_base}/ocpi/emsp/2.2.1/commands/callback"
        payload = {
            "response_url": response_url,
            "session_id": session_id
        }
        try:
            res = requests.post(url, json=payload, headers=self.headers, timeout=15)
            log_ocpi_activity('OUT', 'commands', url, 'POST', res.status_code, f'STOP_SESSION -> callback: {response_url}', {'payload': payload, 'response': res.text[:500]})
            return res.json() if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            log_ocpi_activity('OUT', 'commands', url, 'POST', 0, f'STOP_SESSION failed: {e}')
            return {"error": str(e)}

    def get_sessions(self, session_id: str = "") -> dict:
        """Fetch sessions from CPO: GET /ocpi/cpo/2.2.1/sessions or GET /ocpi/cpo/2.2.1/sessions/{id}"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/sessions"
        if session_id:
            url = f"{url}/{session_id.strip()}"
        try:
            res = requests.get(url, headers=self.headers, timeout=12)
            try:
                res_json = res.json()
            except Exception:
                res_json = {"raw": res.text}
            log_ocpi_activity('OUT', 'sessions', url, 'GET', res.status_code, f'Get Sessions {"(" + session_id + ")" if session_id else ""}', {'response': res_json})
            return res_json if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            log_ocpi_activity('OUT', 'sessions', url, 'GET', 0, f'Get Sessions failed: {e}')
            return {"error": str(e)}

    def get_cdrs(self, cdr_id: str = "") -> dict:
        """Fetch CDRs from CPO: GET /ocpi/cpo/2.2.1/cdrs or GET /ocpi/cpo/2.2.1/cdrs/{id}"""
        url = f"{self.config.cpo_url.rstrip('/')}/ocpi/cpo/2.2.1/cdrs"
        if cdr_id:
            url = f"{url}/{cdr_id.strip()}"
        try:
            res = requests.get(url, headers=self.headers, timeout=12)
            try:
                res_json = res.json()
            except Exception:
                res_json = {"raw": res.text}
            log_ocpi_activity('OUT', 'cdrs', url, 'GET', res.status_code, f'Get CDRs {"(" + cdr_id + ")" if cdr_id else ""}', {'response': res_json})
            return res_json if res.status_code == 200 else {"error": res.text, "status_code": res.status_code}
        except Exception as e:
            log_ocpi_activity('OUT', 'cdrs', url, 'GET', 0, f'Get CDRs failed: {e}')
            return {"error": str(e)}


