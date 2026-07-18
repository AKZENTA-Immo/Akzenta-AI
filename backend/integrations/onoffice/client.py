import base64
import hashlib
import hmac
import time
from typing import Any

import requests

from backend.integrations.onoffice.exceptions import OnOfficeAuthenticationError, OnOfficeResponseError, OnOfficeTimeout, OnOfficeUnavailable

READ_ACTION = "urn:onoffice-de-ns:smart:2.5:smartml:action:read"
GET_ACTION = "urn:onoffice-de-ns:smart:2.5:smartml:action:get"

def create_hmac_v2(timestamp: int, token: str, resource_type: str, action_id: str, secret: str) -> str:
    message = f"{timestamp}{token}{resource_type}{action_id}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")

class OnOfficeClient:
    def __init__(self, api_url: str, token: str, secret: str, timeout: float = 15, session=None, clock=None):
        self.api_url, self.token, self.secret, self.timeout = api_url, token, secret, timeout
        self.session = session or requests.Session()
        self.clock = clock or time.time

    def request(self, action_id: str, resource_type: str, *, resource_id: str = "", parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        timestamp = int(self.clock())
        action = {"actionid": action_id, "resourceid": resource_id, "identifier": "", "resourcetype": resource_type,
            "timestamp": timestamp, "hmac_version": 2, "hmac": create_hmac_v2(timestamp, self.token, resource_type, action_id, self.secret), "parameters": parameters or {}}
        try:
            response = self.session.post(self.api_url, json={"token": self.token, "request": {"actions": [action]}}, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except requests.Timeout as exc: raise OnOfficeTimeout("onOffice hat nicht rechtzeitig geantwortet.") from exc
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403}:
                raise OnOfficeAuthenticationError("onOffice-Authentifizierung fehlgeschlagen.") from exc
            raise OnOfficeUnavailable("onOffice ist derzeit nicht erreichbar.") from exc
        except requests.RequestException as exc: raise OnOfficeUnavailable("onOffice ist derzeit nicht erreichbar.") from exc
        except ValueError as exc: raise OnOfficeResponseError("onOffice lieferte keine gültige Antwort.") from exc
        results = body.get("response", {}).get("results", []) if isinstance(body, dict) else []
        if not results: raise OnOfficeResponseError("onOffice lieferte kein verwertbares Ergebnis.")
        result = results[0]
        status = result.get("status", {})
        error_code = int(status.get("errorcode", 0) or 0)
        if error_code:
            message = str(status.get("message", ""))
            if "auth" in message.casefold() or error_code in {401, 403}: raise OnOfficeAuthenticationError("onOffice-Authentifizierung fehlgeschlagen.")
            raise OnOfficeResponseError(f"onOffice-Anfrage fehlgeschlagen (Code {error_code}).")
        return result
