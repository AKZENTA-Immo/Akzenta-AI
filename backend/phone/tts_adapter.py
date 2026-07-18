from typing import Protocol, runtime_checkable


class TextToSpeechError(RuntimeError):
    pass


@runtime_checkable
class TTSAdapter(Protocol):
    """Exchangeable local adapter for Piper, Coqui or another offline engine."""

    def synthesize(self, text: str, *, language: str = "de") -> bytes: ...


class UnconfiguredTTSAdapter:
    def synthesize(self, text: str, *, language: str = "de") -> bytes:
        raise TextToSpeechError("Keine lokale TTS-Engine konfiguriert.")
