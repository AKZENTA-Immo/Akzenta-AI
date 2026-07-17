from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend import config
from backend.main import app
from backend.services.dokument_reader import DokumentLesefehler, lese_dokument
from backend.services.dokument_scanner import DokumentPfadFehler, dokument_id, relevante_dokumente, sicherer_pfad


@pytest.fixture
def dropbox(tmp_path, monkeypatch):
    basis = tmp_path / "Dropbox"
    basis.mkdir()
    monkeypatch.setattr(config, "DROPBOX_PATH", basis)
    return basis


def test_dateitypfilter_und_relative_api_pfade(dropbox):
    (dropbox / "Unterordner").mkdir()
    (dropbox / "Unterordner" / "a.PDF").touch()
    (dropbox / "bild.jpg").touch()
    (dropbox / "notiz.txt").write_text("Hallo", encoding="utf-8")

    dateien = relevante_dokumente()
    assert [d.suffix.lower() for d in dateien] == [".txt", ".pdf"]
    antwort = TestClient(app).get("/dokumente")
    assert antwort.status_code == 200
    inhalt = antwort.json()
    assert all(str(dropbox) not in d["pfad"] for d in inhalt["dateien"])
    assert {d["pfad"] for d in inhalt["dateien"]} == {"notiz.txt", "Unterordner/a.PDF"}


def test_pfadsicherheit(dropbox, tmp_path):
    ausserhalb = tmp_path / "geheim.txt"
    ausserhalb.write_text("geheim", encoding="utf-8")
    with pytest.raises(DokumentPfadFehler):
        sicherer_pfad(ausserhalb)
    assert TestClient(app).get(f"/dokumente/{dokument_id('../geheim.txt')}").status_code == 404


def test_txt_auslesen_und_endpunkte(dropbox):
    datei = dropbox / "notiz.txt"
    datei.write_text("Ä" * 3100, encoding="utf-8")
    doc_id = TestClient(app).get("/dokumente").json()["dateien"][0]["id"]
    detail = TestClient(app).get(f"/dokumente/{doc_id}")
    volltext = TestClient(app).get(f"/dokumente/{doc_id}/text")
    assert detail.status_code == 200
    assert len(detail.json()["textvorschau"]) == 3000
    assert len(volltext.json()["text"]) == 3100


def test_docx_auslesen(dropbox):
    datei = dropbox / "test.docx"
    doc = Document()
    doc.add_paragraph("DOCX-Inhalt")
    doc.save(datei)
    assert "DOCX-Inhalt" in lese_dokument(datei)


def test_pdf_auslesen(dropbox):
    datei = dropbox / "test.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with datei.open("wb") as stream:
        writer.write(stream)
    assert lese_dokument(datei) == ""


def test_fehlerhafte_datei_und_lesestatus(dropbox):
    kaputt = dropbox / "kaputt.pdf"
    kaputt.write_bytes(b"kein pdf")
    with pytest.raises(DokumentLesefehler):
        lese_dokument(kaputt)
    antwort = TestClient(app).get("/dokumente/lesestatus")
    assert antwort.status_code == 200
    assert antwort.json()["nach_dateityp"][".pdf"]["fehlerhaft"] == 1
    assert antwort.json()["fehler_nach_dateityp"] == {".pdf": 1}


def test_fehler_endpunkt_listet_nur_nicht_lesbare_dokumente(dropbox):
    (dropbox / "lesbar.txt").write_text("Inhalt", encoding="utf-8")
    kaputt = dropbox / "Unterordner" / "kaputt.docx"
    kaputt.parent.mkdir()
    kaputt.write_bytes(b"kein Word-Dokument")

    antwort = TestClient(app).get("/dokumente/fehler")

    assert antwort.status_code == 200
    inhalt = antwort.json()
    assert inhalt["anzahl"] == 1
    assert inhalt["dokumente"] == [
        {
            "dokument_id": dokument_id("Unterordner/kaputt.docx"),
            "pfad": "Unterordner/kaputt.docx",
            "dateiname": "kaputt.docx",
            "dateiendung": ".docx",
            "fehlermeldung": "Word-Dokument konnte nicht gelesen werden. Die Datei ist möglicherweise beschädigt oder nicht unterstützt.",
        }
    ]
    assert str(dropbox) not in antwort.text
    assert "lesbar.txt" not in antwort.text


def test_fehler_endpunkt_ist_keine_dokument_id(dropbox):
    antwort = TestClient(app).get("/dokumente/fehler")
    assert antwort.status_code == 200
    assert antwort.json() == {"status": "ok", "anzahl": 0, "dokumente": []}


def test_fehlender_ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DROPBOX_PATH", tmp_path / "fehlt")
    antwort = TestClient(app).get("/dokumente")
    assert antwort.status_code == 503
    assert str(tmp_path) not in antwort.text
