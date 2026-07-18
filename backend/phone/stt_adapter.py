from typing import Protocol, runtime_checkable


class SpeechToTextError(RuntimeError):
    pass


@runtime_checkable
class STTAdapter(Protocol):
    """Exchangeable local adapter for whisper.cpp, faster-whisper or Vosk."""

    def transcribe(self, audio: bytes, *, language: str = "de") -> str: ...


class UnconfiguredSTTAdapter:
    def transcribe(self, audio: bytes, *, language: str = "de") -> str:
        raise SpeechToTextError("Keine lokale STT-Engine konfiguriert.")
