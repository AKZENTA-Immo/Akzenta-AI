from urllib.parse import urlsplit, urlunsplit

import requests

from backend import config


class OllamaChatFehler(RuntimeError):
    pass


class OllamaNichtErreichbar(OllamaChatFehler):
    pass


class OllamaTimeout(OllamaChatFehler):
    pass


class ChatModellFehlt(OllamaChatFehler):
    pass


class UngueltigeModellAntwort(OllamaChatFehler):
    pass


class OllamaChatService:
    def __init__(self, url: str | None = None, modell: str | None = None, timeout: int | None = None):
        self.url = url or config.OLLAMA_CHAT_URL
        self.modell = modell or config.OLLAMA_CHAT_MODEL
        self.timeout = timeout or config.OLLAMA_REQUEST_TIMEOUT

    def antworte(self, system_prompt: str, benutzer_prompt: str) -> str:
        try:
            antwort = requests.post(
                self.url,
                json={
                    "model": self.modell,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": benutzer_prompt},
                    ],
                    "options": {"temperature": 0.1},
                },
                timeout=self.timeout,
            )
            antwort.raise_for_status()
            daten = antwort.json()
        except requests.Timeout as exc:
            raise OllamaTimeout("Zeitüberschreitung bei der lokalen Antwortgenerierung durch Ollama.") from exc
        except requests.ConnectionError as exc:
            raise OllamaNichtErreichbar("Ollama ist für den Dokumentenchat nicht erreichbar.") from exc
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise ChatModellFehlt(f"Chat-Modell '{self.modell}' ist in Ollama nicht verfügbar.") from exc
            raise OllamaChatFehler("Ollama konnte keine Chat-Antwort erzeugen.") from exc
        except (requests.RequestException, ValueError) as exc:
            raise UngueltigeModellAntwort("Ollama lieferte keine gültige Chat-Antwort.") from exc
        inhalt = daten.get("message", {}).get("content")
        if not isinstance(inhalt, str) or not inhalt.strip():
            raise UngueltigeModellAntwort("Ollama lieferte eine leere oder ungültige Chat-Antwort.")
        return inhalt.strip()

    def modellstatus(self) -> tuple[bool, bool, list[str]]:
        teile = urlsplit(self.url)
        tags_url = urlunsplit((teile.scheme, teile.netloc, "/api/tags", "", ""))
        try:
            antwort = requests.get(tags_url, timeout=min(self.timeout, 10))
            antwort.raise_for_status()
            modelle = [m.get("name", "") for m in antwort.json().get("models", [])]
        except (requests.RequestException, ValueError):
            return False, False, []
        vorhanden = any(name == self.modell or name.split(":", 1)[0] == self.modell for name in modelle)
        return True, vorhanden, modelle
