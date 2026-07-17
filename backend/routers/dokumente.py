from collections import Counter, defaultdict
from datetime import datetime, timezone
import mimetypes
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend import config
from backend.services.dokument_reader import DokumentLesefehler, lese_dokument
from backend.services.dokument_scanner import (
    DokumentPfadFehler, finde_dokument, metadaten, relevante_dokumente, relativer_pfad,
)
from backend.services.chroma_service import ChromaFehler, ChromaService


router = APIRouter(prefix="/dokumente", tags=["Dokumente"])


def _dateien():
    try:
        return relevante_dokumente()
    except DokumentPfadFehler as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _holen(dokument_id: str):
    try:
        datei = finde_dokument(dokument_id)
    except DokumentPfadFehler as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if datei is None:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return datei


def _index_status() -> dict:
    try:
        return ChromaService().lade_status().get("dokumente", {})
    except ChromaFehler:
        return {}


def _hauptordner(relativ: str) -> str:
    return relativ.split("/", 1)[0] if "/" in relativ else "Stammordner"


def _sichere_metadaten(datei: Path, index: dict, text_laden: bool = False) -> dict:
    basis = metadaten(datei)
    doc_id = basis["id"]
    index_daten = index.get(doc_id, {})
    lesbar, lesefehler, text = True, None, None
    # Ein erfolgreich indexiertes Dokument wurde bereits vollständig gelesen.
    # Nur nicht indexierte Dateien müssen für den Lesestatus erneut geprüft werden.
    if text_laden or doc_id not in index:
        try:
            text = lese_dokument(datei)
        except DokumentLesefehler as exc:
            lesbar, lesefehler = False, str(exc)
    endung = basis["endung"]
    relativ = basis["pfad"]
    return {
        "dokument_id": doc_id,
        "dateiname": basis["name"],
        "dateiendung": endung,
        "relativer_pfad": relativ,
        "hauptordner": _hauptordner(relativ),
        "dateigroesse_bytes": basis["groesse_bytes"],
        "geaendert_am": datetime.fromtimestamp(basis["geaendert"], tz=timezone.utc).isoformat(),
        "lesbar": lesbar,
        "lesefehler": lesefehler,
        "indexiert": doc_id in index,
        "abschnitt_anzahl": int(index_daten.get("abschnitte", 0)),
        "seiten_oder_elemente": None,
        "mime_typ": mimetypes.guess_type(datei.name)[0],
        **({"textauszug": (text or "")[:config.VORSCHAU_ZEICHEN]} if text_laden else {}),
    }


@router.get("")
def dokumente(
    suche: str | None = Query(None, max_length=200),
    dateityp: str | None = None,
    hauptordner: str | None = None,
    lesestatus: Literal["lesbar", "fehlerhaft"] | None = None,
    indexstatus: Literal["indexiert", "nicht_indexiert"] | None = None,
    sortierung: Literal["dateiname", "dateityp", "dateigroesse", "geaendert_am", "relativer_pfad"] = "dateiname",
    sortierreihenfolge: Literal["asc", "desc"] = "asc",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    index = _index_status()
    eintraege = [_sichere_metadaten(d, index) for d in _dateien()]
    if suche:
        begriff = suche.casefold().strip()
        eintraege = [d for d in eintraege if any(begriff in str(d[k]).casefold() for k in ("dateiname", "relativer_pfad", "hauptordner", "dateiendung"))]
    if dateityp:
        typ = dateityp.casefold()
        if not typ.startswith("."):
            typ = f".{typ}"
        eintraege = [d for d in eintraege if d["dateiendung"].casefold() == typ]
    if hauptordner:
        eintraege = [d for d in eintraege if d["hauptordner"].casefold() == hauptordner.casefold()]
    if lesestatus:
        eintraege = [d for d in eintraege if d["lesbar"] is (lesestatus == "lesbar")]
    if indexstatus:
        eintraege = [d for d in eintraege if d["indexiert"] is (indexstatus == "indexiert")]
    schluessel = {"dateiname": "dateiname", "dateityp": "dateiendung", "dateigroesse": "dateigroesse_bytes", "geaendert_am": "geaendert_am", "relativer_pfad": "relativer_pfad"}[sortierung]
    eintraege.sort(key=lambda d: (d[schluessel].casefold() if isinstance(d[schluessel], str) else d[schluessel]), reverse=sortierreihenfolge == "desc")
    gesamt = len(eintraege)
    seite = eintraege[offset:offset + limit]
    # Legacy-Felder bleiben für bestehende lokale Clients bis zu einer späteren
    # kontrollierten API-Migration erhalten.
    return {"gesamt": gesamt, "limit": limit, "offset": offset, "dokumente": seite, "status": "ok", "anzahl": gesamt, "dateien": [{"id": d["dokument_id"], "name": d["dateiname"], "pfad": d["relativer_pfad"], "endung": d["dateiendung"], "ordner": str(Path(d["relativer_pfad"]).parent).replace("\\", "/"), "groesse_bytes": d["dateigroesse_bytes"], "geaendert": datetime.fromisoformat(d["geaendert_am"]).timestamp()} for d in seite]}


@router.get("/statistik")
def dokumente_statistik():
    dateien = _dateien()
    index = _index_status()
    eintraege = [_sichere_metadaten(d, index) for d in dateien]
    nach_endung = Counter(d["dateiendung"] for d in eintraege)
    nach_hauptordner = Counter(
        (relativer_pfad(d).split("/", 1)[0] if "/" in relativer_pfad(d) else "Stammordner") for d in dateien
    )
    indexiert = sum(d["indexiert"] for d in eintraege)
    lesbar = sum(d["lesbar"] for d in eintraege)
    nach_dateityp = dict(sorted(nach_endung.items()))
    return {"gesamt": len(dateien), "gesamtzahl": len(dateien), "status": "ok", "nach_dateityp": nach_dateityp, "nach_endung": nach_dateityp, "nach_hauptordner": dict(sorted(nach_hauptordner.items())), "lesbar": lesbar, "fehlerhaft": len(dateien) - lesbar, "indexiert": indexiert, "nicht_indexiert": len(dateien) - indexiert, "gesamtgroesse_bytes": sum(d["dateigroesse_bytes"] for d in eintraege), "abschnitte_gesamt": sum(d["abschnitt_anzahl"] for d in eintraege)}


@router.get("/{dokument_id}/abschnitte")
def dokument_abschnitte(dokument_id: str, limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    _holen(dokument_id)
    try:
        ergebnis = ChromaService().dokument_abschnitte(dokument_id, limit, offset)
    except ChromaFehler as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    abschnitte = []
    for abschnitt_id, text, metadata in ergebnis["eintraege"]:
        metadata = metadata or {}
        text = (text or "")[:5000]
        abschnitte.append({"abschnitt_id": abschnitt_id, "text": text, "seite": metadata.get("seite"), "folie": metadata.get("folie"), "tabellenblatt": metadata.get("tabellenblatt"), "abschnittsnummer": metadata.get("abschnittsnummer", 0), "zeichenanzahl": len(text), "metadaten": {k: v for k, v in metadata.items() if k not in {"pfad", "dateiname", "dokument_id"}}})
    return {"gesamt": ergebnis["gesamt"], "limit": limit, "offset": offset, "abschnitte": abschnitte}


@router.get("/lesestatus")
def lesestatus():
    status = defaultdict(lambda: {"erfolgreich": 0, "fehlerhaft": 0})
    for datei in _dateien():
        try:
            lese_dokument(datei)
            status[datei.suffix.lower()]["erfolgreich"] += 1
        except DokumentLesefehler:
            status[datei.suffix.lower()]["fehlerhaft"] += 1
    gesamt = {"erfolgreich": sum(v["erfolgreich"] for v in status.values()), "fehlerhaft": sum(v["fehlerhaft"] for v in status.values())}
    fehler_nach_dateityp = {
        endung: werte["fehlerhaft"]
        for endung, werte in sorted(status.items())
        if werte["fehlerhaft"] > 0
    }
    return {
        "status": "ok",
        "gesamt": gesamt,
        "nach_dateityp": dict(sorted(status.items())),
        "fehler_nach_dateityp": fehler_nach_dateityp,
    }


@router.get("/fehler")
def fehlerhafte_dokumente():
    fehler = []
    for datei in _dateien():
        try:
            lese_dokument(datei)
        except DokumentLesefehler as exc:
            daten = metadaten(datei)
            fehler.append(
                {
                    "dokument_id": daten["id"],
                    "pfad": daten["pfad"],
                    "dateiname": daten["name"],
                    "dateiendung": daten["endung"],
                    "fehlermeldung": str(exc),
                }
            )
    return {"status": "ok", "anzahl": len(fehler), "dokumente": fehler}


@router.get("/{dokument_id}/text")
def dokument_text(dokument_id: str):
    datei = _holen(dokument_id)
    try:
        return {"id": dokument_id, "pfad": relativer_pfad(datei), "text": lese_dokument(datei)}
    except DokumentLesefehler as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{dokument_id}")
def dokument_detail(dokument_id: str):
    datei = _holen(dokument_id)
    daten = _sichere_metadaten(datei, _index_status(), True)
    daten["abschnittsmetadaten"] = {"verfuegbar": daten["abschnitt_anzahl"] > 0}
    daten.update({"id": daten["dokument_id"], "name": daten["dateiname"], "pfad": daten["relativer_pfad"], "endung": daten["dateiendung"], "textvorschau": daten["textauszug"]})
    return daten
