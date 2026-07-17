from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.services.chroma_service import ChromaService
from backend.services.index_service import IndexService, abschnitt_id, teile_text, teile_text_mit_quelle


class FakeEmbeddings:
    modell = "test-embedding"

    def embed(self, texte):
        return [[float(len(text)), 1.0] for text in texte]


class FakeCollection:
    def __init__(self, chroma):
        self.chroma = chroma

    def delete(self, ids=None, where=None):
        if ids:
            for abschnitt in ids:
                self.chroma.eintraege.pop(abschnitt, None)


class FakeChroma:
    collection_name = "test_collection"

    def __init__(self):
        self.status = {"dokumente": {}, "letzte_indexierung": None}
        self.eintraege = {}

    def lade_status(self):
        return deepcopy(self.status)

    def speichere_status(self, dokumente):
        self.status = {"dokumente": deepcopy(dokumente), "letzte_indexierung": "2026-07-17T12:00:00+00:00"}
        return self.status["letzte_indexierung"]

    def upsert(self, ids, texte, metadaten, embeddings):
        for i, text, metadata, embedding in zip(ids, texte, metadaten, embeddings):
            self.eintraege[i] = {"text": text, "metadata": metadata, "embedding": embedding}

    def entferne_dokument(self, dokument_id):
        self.eintraege = {k: v for k, v in self.eintraege.items() if v["metadata"]["dokument_id"] != dokument_id}

    def collection(self):
        return FakeCollection(self)

    def anzahl_abschnitte(self):
        return len(self.eintraege)

    def leere_collection(self):
        self.eintraege = {}
        self.status = {"dokumente": {}, "letzte_indexierung": None}


@pytest.fixture
def test_dropbox(tmp_path, monkeypatch):
    basis = tmp_path / "Dropbox"
    basis.mkdir()
    monkeypatch.setattr(config, "DROPBOX_PATH", basis)
    monkeypatch.setattr(config, "ABSCHNITT_ZEICHEN", 10)
    monkeypatch.setattr(config, "ABSCHNITT_UEBERLAPPUNG", 2)
    return basis


def test_textzerlegung_mit_ueberlappung():
    abschnitte = list(teile_text("abcdefghijklmnopqrst", groesse=10, ueberlappung=3))
    assert abschnitte == ["abcdefghij", "hijklmnopq", "opqrst"]
    assert abschnitte[0][-3:] == abschnitte[1][:3]


def test_leere_abschnitte_werden_ignoriert():
    assert list(teile_text("   \n\t  ")) == []


def test_stabile_abschnitts_ids():
    assert abschnitt_id("dokument", 2) == abschnitt_id("dokument", 2)
    assert abschnitt_id("dokument", 2) != abschnitt_id("dokument", 3)


def test_tabellenblatt_metadaten_werden_uebernommen():
    teile = list(teile_text_mit_quelle("[Tabellenblatt: Mieten]\nZeile mit Inhalt", 30, 5))
    assert teile[0][1] == {"tabellenblatt": "Mieten"}
    assert teile[-1][1] == {"tabellenblatt": "Mieten"}


def test_neues_dokument(test_dropbox):
    (test_dropbox / "neu.txt").write_text("abcdefghijklmnop", encoding="utf-8")
    chroma = FakeChroma()
    ergebnis = IndexService(chroma, FakeEmbeddings()).indexiere()
    assert ergebnis["neu_indexiert"] == 1
    assert ergebnis["abschnitte_gesamt"] == 2


def test_indexierung_mit_lokaler_chromadb(test_dropbox, tmp_path):
    (test_dropbox / "chroma.txt").write_text("lokale semantische Wissensbasis", encoding="utf-8")
    chroma = ChromaService(tmp_path / "chroma", "test_wissensbasis")
    ergebnis = IndexService(chroma, FakeEmbeddings()).indexiere()
    assert ergebnis["neu_indexiert"] == 1
    assert chroma.anzahl_abschnitte() > 0
    assert (tmp_path / "chroma" / "index_state.json").exists()
    neuaufbau = IndexService(chroma, FakeEmbeddings()).indexiere(vollstaendig=True)
    assert neuaufbau["neu_indexiert"] == 1


def test_unveraendertes_dokument_wird_uebersprungen(test_dropbox):
    (test_dropbox / "gleich.txt").write_text("abcdefghijk", encoding="utf-8")
    chroma = FakeChroma()
    service = IndexService(chroma, FakeEmbeddings())
    service.indexiere()
    ergebnis = service.indexiere()
    assert ergebnis["unveraendert"] == 1
    assert ergebnis["neu_indexiert"] == 0


def test_vollstaendiger_reindex_indexiert_unveraenderte_datei_neu(test_dropbox):
    (test_dropbox / "gleich.txt").write_text("abcdefghijk", encoding="utf-8")
    chroma = FakeChroma()
    service = IndexService(chroma, FakeEmbeddings())
    service.indexiere()
    ergebnis = service.indexiere(vollstaendig=True)
    assert ergebnis["neu_indexiert"] == 1
    assert ergebnis["unveraendert"] == 0


def test_geaendertes_dokument_wird_aktualisiert(test_dropbox):
    datei = test_dropbox / "aenderung.txt"
    datei.write_text("alter Inhalt", encoding="utf-8")
    chroma = FakeChroma()
    service = IndexService(chroma, FakeEmbeddings())
    service.indexiere()
    datei.write_text("neuer und deutlich längerer Inhalt", encoding="utf-8")
    ergebnis = service.indexiere()
    assert ergebnis["aktualisiert"] == 1


def test_entferntes_dokument_wird_aus_index_geloescht(test_dropbox):
    datei = test_dropbox / "entfernt.txt"
    datei.write_text("wird indexiert", encoding="utf-8")
    chroma = FakeChroma()
    service = IndexService(chroma, FakeEmbeddings())
    service.indexiere()
    datei.unlink()
    ergebnis = service.indexiere()
    assert ergebnis["entfernt"] == 1
    assert chroma.eintraege == {}


def test_leeres_dokument_ist_einzelfehler(test_dropbox):
    (test_dropbox / "leer.txt").write_text("  ", encoding="utf-8")
    (test_dropbox / "gut.txt").write_text("Inhalt", encoding="utf-8")
    ergebnis = IndexService(FakeChroma(), FakeEmbeddings()).indexiere()
    assert ergebnis["neu_indexiert"] == 1
    assert ergebnis["fehlerhaft"] == 1
    assert ergebnis["fehler"] == [{"pfad": "leer.txt", "ursache": "Dokument enthält keinen indexierbaren Text."}]


def test_interne_fehler_geben_keine_absoluten_pfade_aus(test_dropbox):
    class UnsichereEmbeddings:
        def embed(self, texte):
            raise ValueError(r"Fehler in C:\Users\Privat\geheim.txt")

    (test_dropbox / "fehler.txt").write_text("Inhalt", encoding="utf-8")
    ergebnis = IndexService(FakeChroma(), UnsichereEmbeddings()).indexiere()
    assert ergebnis["fehler"][0]["ursache"] == "Dokument konnte nicht indexiert werden."
    assert "C:\\Users" not in str(ergebnis)


def test_semantische_suche_und_keine_absoluten_pfade(monkeypatch, tmp_path):
    class SucheChroma:
        def suche(self, embedding, limit):
            return [{
                "text": "Hamburger Immobilie",
                "relevanz": 0.91,
                "metadata": {"dokument_id": "abc", "dateiname": "expose.txt", "pfad": "Exposes/expose.txt", "abschnittsnummer": 0},
            }]

    monkeypatch.setattr("backend.routers.wissensbasis.ChromaService", SucheChroma)
    monkeypatch.setattr("backend.routers.wissensbasis.OllamaEmbeddingService", lambda: FakeEmbeddings())
    antwort = TestClient(app).get("/wissensbasis/suche", params={"q": "Immobilie", "limit": 5})
    assert antwort.status_code == 200
    assert antwort.json()["treffer"][0]["pfad"] == "Exposes/expose.txt"
    assert str(tmp_path) not in antwort.text


def test_status_zeigt_nur_relativen_speicherort(monkeypatch):
    class StatusChroma:
        collection_name = "test_collection"

        def lade_status(self):
            return {"dokumente": {"abc": {}}, "letzte_indexierung": "2026-07-17T12:00:00+00:00"}

        def anzahl_abschnitte(self):
            return 3

        def relativer_speicherort(self):
            return "data/chroma"

    monkeypatch.setattr("backend.routers.wissensbasis.ChromaService", StatusChroma)
    antwort = TestClient(app).get("/wissensbasis/status")
    assert antwort.status_code == 200
    assert antwort.json()["chromadb_erreichbar"] is True
    assert antwort.json()["speicherort"] == "data/chroma"
    assert ":\\" not in antwort.text


@pytest.mark.parametrize("params", [{"q": ""}, {"q": "   "}, {"q": "test", "limit": 0}, {"q": "test", "limit": 21}])
def test_suchvalidierung(params):
    assert TestClient(app).get("/wissensbasis/suche", params=params).status_code == 422
