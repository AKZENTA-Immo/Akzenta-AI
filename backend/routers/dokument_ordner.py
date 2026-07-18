from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException

from backend.services.dokument_scanner import DokumentPfadFehler, relevante_dokumente, relativer_pfad


router = APIRouter(prefix="/dokumente", tags=["Dokumente"])


def _neuer_knoten(name: str, pfad: str) -> dict:
    return {
        "name": name,
        "pfad": pfad,
        "dokumente": 0,
        "unterordner": {},
    }


@router.get("/ordner")
def dokument_ordner():
    try:
        dateien = relevante_dokumente()
    except DokumentPfadFehler as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    wurzel = _neuer_knoten("Alle Dokumente", "")
    dateitypen: dict[str, int] = defaultdict(int)

    for datei in dateien:
        relativ = PurePosixPath(relativer_pfad(datei))
        wurzel["dokumente"] += 1
        dateitypen[datei.suffix.lower()] += 1

        aktueller_knoten = wurzel
        teile = relativ.parts[:-1]
        bisheriger_pfad: list[str] = []

        for teil in teile:
            bisheriger_pfad.append(teil)
            unterordner = aktueller_knoten["unterordner"]
            if teil not in unterordner:
                unterordner[teil] = _neuer_knoten(teil, "/".join(bisheriger_pfad))
            aktueller_knoten = unterordner[teil]
            aktueller_knoten["dokumente"] += 1

    def serialisieren(knoten: dict) -> dict:
        return {
            "name": knoten["name"],
            "pfad": knoten["pfad"],
            "dokumente": knoten["dokumente"],
            "unterordner": [
                serialisieren(kind)
                for _, kind in sorted(knoten["unterordner"].items(), key=lambda eintrag: eintrag[0].casefold())
            ],
        }

    return {
        "status": "ok",
        "wurzel": serialisieren(wurzel),
        "dateitypen": dict(sorted(dateitypen.items())),
    }
