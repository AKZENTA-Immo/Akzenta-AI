import re
from dataclasses import dataclass

from backend.rag.loader import LoadedDocument


@dataclass(frozen=True)
class Chunk:
    position: int
    text: str
    page: int | None
    section: str | None


def chunk_document(document: LoadedDocument, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunkgröße und Overlap sind ungültig.")
    text = document.text.strip()
    chunks, start, page, section = [], 0, None, None
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n\n", start, end), text.rfind(". ", start, end))
            if boundary > start + size // 2:
                end = boundary + (2 if text[boundary:boundary + 2] == ". " else 0)
        value = text[start:end].strip()
        pages = re.findall(r"\[(?:Seite|Folie) (\d+)\]", value)
        sheets = re.findall(r"\[Tabellenblatt: ([^\]]+)\]", value)
        headings = re.findall(r"(?m)^(?:#{1,6}\s+|ABSCHNITT:\s*)(.+)$", value)
        if pages: page = int(pages[-1])
        if sheets: section = sheets[-1]
        elif headings: section = headings[-1].strip()
        if value: chunks.append(Chunk(len(chunks), value, page, section))
        if end >= len(text): break
        start = max(start + 1, end - overlap)
    return chunks
