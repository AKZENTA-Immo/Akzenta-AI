from fastapi import APIRouter, HTTPException, Path

from backend.integrations.onoffice.adapter import onoffice_adapter
from backend.integrations.onoffice.exceptions import OnOfficeAuthenticationError, OnOfficeConfigurationError, OnOfficeDisabled, OnOfficeResponseError, OnOfficeTimeout, OnOfficeUnavailable
from backend.integrations.onoffice.models import OnOfficeRecord, OnOfficeSearchRequest, OnOfficeSearchResponse, OnOfficeStatus

router = APIRouter(prefix="/integrations/onoffice", tags=["onOffice (read-only)"])

def safe_call(call):
    try: return call()
    except OnOfficeDisabled as exc: raise HTTPException(409, detail=str(exc)) from exc
    except OnOfficeConfigurationError as exc: raise HTTPException(503, detail=str(exc)) from exc
    except OnOfficeAuthenticationError as exc: raise HTTPException(502, detail=str(exc)) from exc
    except OnOfficeTimeout as exc: raise HTTPException(504, detail=str(exc)) from exc
    except OnOfficeUnavailable as exc: raise HTTPException(503, detail=str(exc)) from exc
    except OnOfficeResponseError as exc: raise HTTPException(502, detail=str(exc)) from exc
    except LookupError as exc: raise HTTPException(404, detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(500, detail="onOffice-Leseanfrage konnte nicht sicher verarbeitet werden.") from exc

@router.get("/status", response_model=OnOfficeStatus)
def status(): return onoffice_adapter.status()
@router.post("/contacts/search", response_model=OnOfficeSearchResponse)
def contacts_search(request: OnOfficeSearchRequest): return safe_call(lambda: onoffice_adapter.search_contacts(request))
@router.get("/contacts/{contact_id}", response_model=OnOfficeRecord)
def contact(contact_id: int = Path(ge=1)): return safe_call(lambda: onoffice_adapter.get_contact(contact_id))
@router.post("/estates/search", response_model=OnOfficeSearchResponse)
def estates_search(request: OnOfficeSearchRequest): return safe_call(lambda: onoffice_adapter.search_estates(request))
@router.get("/estates/{estate_id}", response_model=OnOfficeRecord)
def estate(estate_id: int = Path(ge=1)): return safe_call(lambda: onoffice_adapter.get_estate(estate_id))
