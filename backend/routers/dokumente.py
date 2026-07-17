from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException

from backend import config
from backend.services.dokument_reader import DokumentLesefehler, lese_dokument
from backend.services.dokument_scanner import (
    DokumentPfadFehler, finde_dokument, metadaten, relevante_dokumente, relativer_pfad,
)


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


@router.get("")
def dokumente():
    dateien = _dateien()
    return {"status": "ok", "anzahl": len(dateien), "dateien": [metadaten(d) for d in dateien]}


@router.get("/statistik")
def dokumente_statistik():
    dateien = _dateien()
    nach_endung = Counter(d.suffix.lower() for d in dateien)
    nach_hauptordner = Counter(
        (relativer_pfad(d).split("/", 1)[0] if "/" in relativer_pfad(d) else "Stammordner") for d in dateien
    )
    return {"status": "ok", "gesamtzahl": len(dateien), "nach_endung": dict(sorted(nach_endung.items())), "nach_hauptordner": dict(sorted(nach_hauptordner.items()))}


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
    try:
        text = lese_dokument(datei)
    except DokumentLesefehler as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**metadaten(datei), "textvorschau": text[:config.VORSCHAU_ZEICHEN]}
