from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.services.chat_service import DokumentChatService
from backend.services.index_service import IndexService
from backend.services.text_normalizer import normalize_api_data, normalize_unicode_text


def test_korrekter_deutscher_text_bleibt_unveraendert():
    text = "ä ö ü Ä Ö Ü ß – „deutsche Anführungszeichen“ • 25 €"
    assert normalize_unicode_text(text) == text


def test_eindeutige_mojibake_sequenzen_werden_repariert():
    fehlerhaft = "VermÃ¶gen, GesprÃ¤ch, regelmÃ¤ÃŸig â€“ â€žZitatâ€œ â€¢ 25 â‚¬"
    erwartet = "Vermögen, Gespräch, regelmäßig – „Zitat“ • 25 €"
    assert normalize_unicode_text(fehlerhaft) == erwartet


def test_unicode_wird_nfc_normalisiert_und_steuerzeichen_entfernt():
    assert normalize_unicode_text("a\u0308\x00\nZeile\t2") == "ä\nZeile\t2"


def test_api_daten_werden_rekursiv_normalisiert():
    assert normalize_api_data({"text": ["schÃ¶n", "bereits schön"]}) == {"text": ["schön", "bereits schön"]}


def test_fastapi_liefert_utf8_json():
    antwort = TestClient(app).get("/")
    assert antwort.status_code == 200
    assert "application/json" in antwort.headers["content-type"]
    assert "charset=utf-8" in antwort.headers["content-type"]
    assert antwort.json()["status"] == "AKZENTA AI läuft"
    assert "läuft".encode("utf-8") in antwort.content


class FakeEmbeddings:
    modell = "nomic-embed-text"

    def embed(self, texte):
        return [[1.0, 0.0] for _ in texte]


class SpeicherChroma:
    def __init__(self):
        self.texte = []
        self.status = {"dokumente": {}, "letzte_indexierung": None}

    def lade_status(self):
        return self.status

    def speichere_status(self, dokumente):
        self.status = {"dokumente": dokumente, "letzte_indexierung": "jetzt"}

    def upsert(self, ids, texte, metadaten, embeddings):
        self.texte.extend(texte)

    def anzahl_abschnitte(self):
        return len(self.texte)

    def entferne_dokument(self, dokument_id):
        pass

    def collection(self):
        return self

    def delete(self, ids=None):
        pass


def test_chromadb_erhaelt_normalisierten_text(tmp_path, monkeypatch):
    dropbox = tmp_path / "Dropbox"
    dropbox.mkdir()
    (dropbox / "mojibake.txt").write_text("VermÃ¶gensobjekt â€¢ regelmäßig", encoding="utf-8")
    monkeypatch.setattr(config, "DROPBOX_PATH", dropbox)
    chroma = SpeicherChroma()
    IndexService(chroma, FakeEmbeddings()).indexiere()
    assert chroma.texte == ["Vermögensobjekt • regelmäßig"]


def test_chat_kontext_und_antwort_enthalten_korrekte_umlaute():
    class ChatChroma:
        def anzahl_abschnitte(self):
            return 1

        def suche(self, embedding, limit):
            return [{
                "text": "regelmÃ¤ÃŸiges VermÃ¶gensobjekt â€¢ Vorteil",
                "relevanz": 0.9,
                "metadata": {
                    "dokument_id": "doc",
                    "dateiname": "leitfaden.txt",
                    "pfad": "Ordner/leitfaden.txt",
                    "abschnittsnummer": 1,
                },
            }]

    class Chat:
        modell = "llama3"

        def __init__(self):
            self.kontext = ""

        def antworte(self, system_prompt, benutzer_prompt):
            self.kontext = benutzer_prompt
            return "Ein regelmÃ¤ÃŸiges VermÃ¶gensobjekt [Quelle 1]."

    chat = Chat()
    antwort = DokumentChatService(ChatChroma(), FakeEmbeddings(), chat).beantworte("Welche Vorteile?", 5)
    assert "regelmäßiges Vermögensobjekt • Vorteil" in chat.kontext
    assert antwort.antwort == "Ein regelmäßiges Vermögensobjekt [Quelle 1]."
    assert antwort.quellen[0].textausschnitt == "regelmäßiges Vermögensobjekt • Vorteil"
