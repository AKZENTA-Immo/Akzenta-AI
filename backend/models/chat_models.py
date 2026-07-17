from pydantic import BaseModel, Field, field_validator

from backend import config


class DokumentChatAnfrage(BaseModel):
    frage: str = Field(min_length=3, max_length=config.CHAT_MAX_QUESTION_CHARS)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("frage")
    @classmethod
    def frage_bereinigen(cls, wert: str) -> str:
        wert = wert.strip()
        if len(wert) < 3:
            raise ValueError("Die Frage muss mindestens 3 Zeichen enthalten.")
        return wert


class ChatQuelle(BaseModel):
    quellen_nummer: int
    dokument_id: str
    dateiname: str
    relativer_pfad: str
    abschnitt: int
    seite: int | None = None
    folie: int | None = None
    tabellenblatt: str | None = None
    relevanz: float
    textausschnitt: str


class DokumentChatAntwort(BaseModel):
    frage: str
    antwort: str
    quellen: list[ChatQuelle]
    verwendetes_chat_modell: str
    verwendetes_embedding_modell: str
    dauer_sekunden: float
