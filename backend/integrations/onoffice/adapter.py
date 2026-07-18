import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend import config
from backend.integrations.onoffice.client import GET_ACTION, READ_ACTION, OnOfficeClient
from backend.integrations.onoffice.exceptions import OnOfficeAuthenticationError, OnOfficeConfigurationError, OnOfficeDisabled, OnOfficeError, OnOfficeTimeout, OnOfficeUnavailable
from backend.integrations.onoffice.models import OnOfficeRecord, OnOfficeSearchRequest, OnOfficeSearchResponse, OnOfficeStatus

# Standardfelder aus der offiziellen API-Dokumentation. Mandantenfelder können
# über ONOFFICE_FIELD_MAPPING_JSON überschrieben und per Feldkonfiguration geprüft werden.
CONTACT_FIELDS = {"onoffice_id": "Id", "salutation": "Anrede", "first_name": "Vorname", "last_name": "Name", "company": "Zusatz1", "email": "Email", "phone": "Telefon1", "mobile": "Mobil", "street": "Strasse", "house_number": "Hausnummer", "postal_code": "Plz", "city": "Ort", "country": "Land", "advisor": "Benutzer", "created_at": "Erfasst", "updated_at": "Aenderung"}
ESTATE_FIELDS = {"onoffice_id": "Id", "external_number": "objektnr_extern", "property_type": "objektart", "marketing_type": "vermarktungsart", "street": "strasse", "house_number": "hausnummer", "postal_code": "plz", "city": "ort", "living_area": "wohnflaeche", "plot_area": "grundstuecksflaeche", "rooms": "anzahl_zimmer", "purchase_price": "kaufpreis", "rental_status": "vermietet", "advisor": "benutzer", "status": "status"}
SEARCHABLE = {"address": {"first_name", "last_name", "company", "email", "postal_code", "city"}, "estate": {"external_number", "property_type", "marketing_type", "postal_code", "city", "status"}}

def safe_api_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    netloc = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

def field_mappings() -> dict[str, dict[str, str]]:
    result = {"address": dict(CONTACT_FIELDS), "estate": dict(ESTATE_FIELDS)}
    if config.ONOFFICE_FIELD_MAPPING_JSON:
        try:
            custom = json.loads(config.ONOFFICE_FIELD_MAPPING_JSON)
            for module in result:
                if isinstance(custom.get(module), dict): result[module].update({str(k): str(v) for k, v in custom[module].items()})
        except (ValueError, TypeError):
            pass
    return result

class OnOfficeReadOnlyAdapter:
    def __init__(self, client: OnOfficeClient | None = None):
        self._client = client
        self.last_check: datetime | None = None

    @property
    def configured(self): return bool(config.ONOFFICE_API_TOKEN and config.ONOFFICE_API_SECRET)
    @property
    def active(self): return config.ONOFFICE_ENABLED and config.ONOFFICE_MODE == "readonly" and self.configured
    @property
    def client(self):
        if not config.ONOFFICE_ENABLED or config.ONOFFICE_MODE != "readonly": raise OnOfficeDisabled("onOffice-Lesemodus ist deaktiviert.")
        if not self.configured: raise OnOfficeConfigurationError("onOffice ist nicht vollständig konfiguriert.")
        return self._client or OnOfficeClient(config.ONOFFICE_API_URL, config.ONOFFICE_API_TOKEN, config.ONOFFICE_API_SECRET, config.ONOFFICE_TIMEOUT_SECONDS)

    def status(self, check_connection: bool = True) -> OnOfficeStatus:
        status = OnOfficeStatus(enabled=config.ONOFFICE_ENABLED, mode=config.ONOFFICE_MODE, configured=self.configured, api_url=safe_api_url(config.ONOFFICE_API_URL))
        if not (check_connection and self.active): return status
        self.last_check = datetime.now(timezone.utc); status.last_check = self.last_check
        try:
            self.get_field_information(["address"])
            status.reachable = status.authenticated = status.permissions_checked = True
        except OnOfficeAuthenticationError: status.reachable = True; status.error_code = "authentication_failed"; status.error_message = "onOffice-Authentifizierung fehlgeschlagen."
        except OnOfficeTimeout: status.error_code = "timeout"; status.error_message = "Zeitüberschreitung beim onOffice-Verbindungstest."
        except OnOfficeUnavailable: status.error_code = "unreachable"; status.error_message = "onOffice ist derzeit nicht erreichbar."
        except OnOfficeError: status.reachable = True; status.error_code = "api_error"; status.error_message = "onOffice-Verbindung konnte nicht sicher geprüft werden."
        return status

    def get_field_information(self, modules: list[str]) -> dict[str, Any]:
        return self.client.request(GET_ACTION, "fields", parameters={"labels": True, "language": "DEU", "modules": modules})

    def _record(self, module: str, raw: dict[str, Any]) -> OnOfficeRecord:
        elements = raw.get("elements", {}) if isinstance(raw, dict) else {}
        mapping = field_mappings()[module]
        data = {target: elements[source] for target, source in mapping.items() if source in elements}
        unknown = sorted(key for key in elements if key not in mapping.values())
        return OnOfficeRecord(id=int(raw.get("id") or elements.get("Id")), type=module, data=data, unmapped_fields=unknown)

    def _read(self, module: str, resource_id: int | None, request: OnOfficeSearchRequest | None = None):
        mapping = field_mappings()[module]
        params: dict[str, Any] = {"data": list(dict.fromkeys(mapping.values()))}
        if request:
            invalid = set(request.filters) - SEARCHABLE[module]
            if invalid: raise ValueError(f"Nicht erlaubte Suchfelder: {', '.join(sorted(invalid))}")
            params.update({"filter": {mapping[key]: [{"op": "like" if isinstance(value, str) else "=", "val": f"%{value}%" if isinstance(value, str) else value}] for key, value in request.filters.items()}, "listlimit": request.limit, "listoffset": request.offset})
        result = self.client.request(READ_ACTION, module, resource_id=str(resource_id or ""), parameters=params)
        data = result.get("data", {}); records = data.get("records", [])
        return records, int(data.get("meta", {}).get("cntabsolute") or len(records))

    def get_contact(self, contact_id: int):
        records, _ = self._read("address", contact_id)
        if not records: raise LookupError("Kontakt nicht gefunden.")
        return self._record("address", records[0])
    def search_contacts(self, request):
        records, total = self._read("address", None, request)
        return OnOfficeSearchResponse(total=total, limit=request.limit, offset=request.offset, records=[self._record("address", item) for item in records])
    def get_estate(self, estate_id: int):
        records, _ = self._read("estate", estate_id)
        if not records: raise LookupError("Immobilie nicht gefunden.")
        return self._record("estate", records[0])
    def search_estates(self, request):
        records, total = self._read("estate", None, request)
        return OnOfficeSearchResponse(total=total, limit=request.limit, offset=request.offset, records=[self._record("estate", item) for item in records])

onoffice_adapter = OnOfficeReadOnlyAdapter()
