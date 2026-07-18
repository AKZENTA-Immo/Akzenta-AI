from dataclasses import dataclass
from pathlib import Path

from backend.services.dokument_reader import lese_dokument
from backend.services.dokument_scanner import metadaten
from backend.services.text_normalizer import normalize_unicode_text


@dataclass(frozen=True)
class LoadedDocument:
    id: str
    filename: str
    path: str
    folder: str
    document_type: str
    modified_at: float
    text: str


def load_document(path: Path) -> LoadedDocument:
    data = metadaten(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        text = "\n\n".join(
            f"[Seite {number}]\n{page.extract_text() or ''}"
            for number, page in enumerate(PdfReader(str(path)).pages, 1)
        )
        text = normalize_unicode_text(text)
    else:
        text = lese_dokument(path)
    return LoadedDocument(
        id=data["id"], filename=data["name"], path=data["pfad"], folder=data["ordner"],
        document_type=data["endung"].lstrip("."), modified_at=data["geaendert"], text=text,
    )
