from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.services.dokument_scanner import dokument_id


@pytest.fixture
def katalog(tmp_path, monkeypatch):
    basis = tmp_path / "Dropbox"
    (basis / "OrdnerA").mkdir(parents=True)
    (basis / "OrdnerB").mkdir()
    (basis / "OrdnerA" / "Alpha.txt").write_text("Alpha Inhalt", encoding="utf-8")
    (basis / "OrdnerB" / "Beta.pdf").write_bytes(b"kein pdf")
    monkeypatch.setattr(config, "DROPBOX_PATH", basis)
    monkeypatch.setattr(
        "backend.routers.dokumente.ChromaService.lade_status",
        lambda self: {"dokumente": {dokument_id("OrdnerA/Alpha.txt"): {"abschnitte": 2}}},
    )
    return basis


def test_liste_pagination_suche_filter_sortierung_und_sichere_pfade(katalog):
    client = TestClient(app)
    antwort = client.get("/dokumente", params={"suche": "alpha", "dateityp": "txt", "hauptordner": "OrdnerA", "indexstatus": "indexiert", "sortierung": "relativer_pfad", "sortierreihenfolge": "desc", "limit": 1, "offset": 0})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["gesamt"] == 1 and len(daten["dokumente"]) == 1
    assert daten["dokumente"][0]["dateiname"] == "Alpha.txt"
    assert str(katalog) not in antwort.text


def test_lesestatus_detail_statistik_und_validierung(katalog):
    client = TestClient(app)
    fehler = client.get("/dokumente", params={"lesestatus": "fehlerhaft"})
    assert fehler.status_code == 200 and fehler.json()["gesamt"] == 1
    doc_id = dokument_id("OrdnerB/Beta.pdf")
    detail = client.get(f"/dokumente/{doc_id}")
    assert detail.status_code == 200 and detail.json()["lesbar"] is False
    assert "textauszug" in detail.json() and str(katalog) not in detail.text
    statistik = client.get("/dokumente/statistik").json()
    assert statistik["gesamt"] == 2 and statistik["fehlerhaft"] == 1 and statistik["abschnitte_gesamt"] == 2
    assert client.get("/dokumente", params={"limit": 101}).status_code == 422
    assert client.get("/dokumente", params={"sortierung": "unbekannt"}).status_code == 422


def test_unbekannte_id_und_abschnittspagination(katalog, monkeypatch):
    client = TestClient(app)
    assert client.get(f"/dokumente/{'0' * 64}").status_code == 404
    doc_id = dokument_id("OrdnerA/Alpha.txt")
    monkeypatch.setattr("backend.routers.dokumente.ChromaService.dokument_abschnitte", lambda self, dokument_id, limit, offset: {"gesamt": 1, "eintraege": [("chunk", "Sicherer Text", {"abschnittsnummer": 0, "seite": 1})]})
    antwort = client.get(f"/dokumente/{doc_id}/abschnitte", params={"limit": 5, "offset": 0})
    assert antwort.status_code == 200
    assert antwort.json()["abschnitte"][0]["text"] == "Sicherer Text"
    assert str(katalog) not in antwort.text
