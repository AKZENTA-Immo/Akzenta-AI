from fastapi import APIRouter, Depends, HTTPException, Request

from backend.phone.call_manager import (CallManager, PhoneEndRequest, PhoneMessageRequest,
                                        PhoneSessionClosed, PhoneSessionNotFound, PhoneStartRequest)
from backend.phone.conversation_memory import PhonePersistenceError
from backend.phone.stt_adapter import SpeechToTextError
from backend.phone.tts_adapter import TextToSpeechError


router = APIRouter(prefix="/phone", tags=["Phone Agent"])


def get_call_manager(request: Request) -> CallManager:
    manager = getattr(request.app.state, "call_manager", None)
    if manager is None:
        manager = CallManager(); request.app.state.call_manager = manager
    return manager


def execute(call):
    try: return call()
    except PhoneSessionNotFound as exc: raise HTTPException(404, str(exc)) from exc
    except PhoneSessionClosed as exc: raise HTTPException(409, str(exc)) from exc
    except PhonePersistenceError as exc: raise HTTPException(503, str(exc)) from exc
    except (SpeechToTextError, TextToSpeechError) as exc: raise HTTPException(503, str(exc)) from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.post("/start")
def start(request: PhoneStartRequest, manager: CallManager = Depends(get_call_manager)): return execute(lambda: manager.start(request))


@router.post("/message")
def message(request: PhoneMessageRequest, manager: CallManager = Depends(get_call_manager)): return execute(lambda: manager.message(request))


@router.post("/end")
def end(request: PhoneEndRequest, manager: CallManager = Depends(get_call_manager)): return execute(lambda: manager.end(request))


@router.get("/session/{session_id}")
def session(session_id: str, manager: CallManager = Depends(get_call_manager)): return execute(lambda: manager.session(session_id))


@router.get("/statistics")
def statistics(manager: CallManager = Depends(get_call_manager)): return execute(manager.statistics)
