import hashlib
import re
import time
from collections.abc import Iterator
from pathlib import Path

from backend import config
from backend.services.chroma_service import ChromaFehler, ChromaService
from backend.services.dokument_reader import DokumentLesefehler, lese_dokument
from backend.services.dokument_scanner import metadaten, relevante_dokumente
from backend.services.embedding_service import EmbeddingFehler, OllamaEmbeddingService


def teile_text(text: str, groesse: int = 1000, ueberlappung: int = 150) -> Iterator[str]:
    if groesse <= 0 or ueberlappung < 0 or ueberlappung >= groesse:
        raise ValueError("Ungültige Werte für Abschnittsgröße oder Überlappung.")
    text = text.strip()
    start = 0
    while start < len(text):
        ende = min(start + groesse, len(text))
        abschnitt = text[start:ende].strip()
        if abschnitt:
            yield abschnitt
        if ende == len(text):
            break
        start = ende - ueberlappung


def abschnitt_id(dokument_id: str, nummer: int) -> str:
    return hashlib.sha256(f"{dokument_id}:{nummer}".encode("utf-8")).hexdigest()


def teile_text_mit_quelle(text: str, groesse: int, ueberlappung: int):
    quelle = {}
    for abschnitt in teile_text(text, groesse, ueberlappung):
        tabellenblaetter = re.findall(r"\[Tabellenblatt: ([^\]]+)\]", abschnitt)
        folien = re.findall(r"\[Folie (\d+)\]", abschnitt)
        if tabellenblaetter:
            quelle = {"tabellenblatt": tabellenblaetter[-1]}
        if folien:
            quelle = {"folie": int(folien[-1])}
        yield abschnitt, dict(quelle)


def _fingerabdruck(datei: Path) -> str:
    stat = datei.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _sichere_ursache(exc: Exception) -> str:
    if isinstance(exc, (DokumentLesefehler, EmbeddingFehler, ChromaFehler)):
        return str(exc)
    return "Dokument konnte nicht indexiert werden."


class IndexService:
    def __init__(self, chroma=None, embeddings=None):
        self.chroma = chroma or ChromaService()
        self.embeddings = embeddings or OllamaEmbeddingService()

    def indexiere(self) -> dict:
        begonnen = time.perf_counter()
        dateien = relevante_dokumente()
        alter_status = self.chroma.lade_status()
        alt = alter_status.get("dokumente", {})
        neu_status = dict(alt)
        aktuelle_ids = set()
        zaehler = {"neu_indexiert": 0, "aktualisiert": 0, "unveraendert": 0, "entfernt": 0, "fehlerhaft": 0}
        fehler = []

        for datei in dateien:
            daten = metadaten(datei)
            doc_id = daten["id"]
            aktuelle_ids.add(doc_id)
            try:
                fingerprint = _fingerabdruck(datei)
                if alt.get(doc_id, {}).get("fingerabdruck") == fingerprint:
                    zaehler["unveraendert"] += 1
                    continue
                text = lese_dokument(datei)
                anzahl_abschnitte = 0
                batch_ids, batch_texte, batch_metadaten = [], [], []
                for nummer, (abschnitt, quelle) in enumerate(
                    teile_text_mit_quelle(text, config.ABSCHNITT_ZEICHEN, config.ABSCHNITT_UEBERLAPPUNG)
                ):
                    metadata = {
                        "dokument_id": doc_id,
                        "pfad": daten["pfad"],
                        "dateiname": daten["name"],
                        "dateiendung": daten["endung"],
                        "hauptordner": daten["pfad"].split("/", 1)[0] if "/" in daten["pfad"] else "Stammordner",
                        "abschnittsnummer": nummer,
                        "aenderungszeit": daten["geaendert"],
                        "dateigroesse": daten["groesse_bytes"],
                        **quelle,
                    }
                    batch_ids.append(abschnitt_id(doc_id, nummer))
                    batch_texte.append(abschnitt)
                    batch_metadaten.append(metadata)
                    anzahl_abschnitte += 1
                    if len(batch_texte) == 32:
                        self.chroma.upsert(batch_ids, batch_texte, batch_metadaten, self.embeddings.embed(batch_texte))
                        batch_ids, batch_texte, batch_metadaten = [], [], []
                if not anzahl_abschnitte:
                    raise DokumentLesefehler("Dokument enthält keinen indexierbaren Text.")
                if batch_texte:
                    self.chroma.upsert(batch_ids, batch_texte, batch_metadaten, self.embeddings.embed(batch_texte))
                alte_anzahl = alt.get(doc_id, {}).get("abschnitte", 0)
                if alte_anzahl > anzahl_abschnitte:
                    self.chroma.collection().delete(ids=[abschnitt_id(doc_id, n) for n in range(anzahl_abschnitte, alte_anzahl)])
                neu_status[doc_id] = {"fingerabdruck": fingerprint, "abschnitte": anzahl_abschnitte, "pfad": daten["pfad"]}
                zaehler["aktualisiert" if doc_id in alt else "neu_indexiert"] += 1
            except Exception as exc:
                zaehler["fehlerhaft"] += 1
                fehler.append({"pfad": daten["pfad"], "ursache": _sichere_ursache(exc)})

        for doc_id in set(alt) - aktuelle_ids:
            try:
                self.chroma.entferne_dokument(doc_id)
                neu_status.pop(doc_id, None)
                zaehler["entfernt"] += 1
            except Exception as exc:
                fehler.append({"pfad": alt[doc_id].get("pfad", "Unbekannt"), "ursache": _sichere_ursache(exc)})

        self.chroma.speichere_status(neu_status)
        return {
            "status": "ok" if not fehler else "mit_fehlern",
            "dokumente_gesamt": len(dateien),
            **zaehler,
            "abschnitte_gesamt": self.chroma.anzahl_abschnitte(),
            "dauer_sekunden": round(time.perf_counter() - begonnen, 3),
            "fehler": fehler,
        }
