import hashlib
from pathlib import Path

from backend import config


class DokumentPfadFehler(ValueError):
    pass


def dropbox_basis() -> Path:
    basis = config.DROPBOX_PATH.expanduser()
    if not basis.exists() or not basis.is_dir():
        raise DokumentPfadFehler("Der konfigurierte Dokumentenordner ist nicht verfügbar.")
    return basis.resolve()


def sicherer_pfad(datei: Path) -> Path:
    basis = dropbox_basis()
    kandidat = datei.resolve(strict=True)
    try:
        kandidat.relative_to(basis)
    except ValueError as exc:
        raise DokumentPfadFehler("Datei liegt außerhalb des Dokumentenordners.") from exc
    if not kandidat.is_file() or kandidat.suffix.lower() not in config.RELEVANTE_ENDUNGEN:
        raise DokumentPfadFehler("Datei ist kein unterstütztes Dokument.")
    return kandidat


def relativer_pfad(datei: Path) -> str:
    return sicherer_pfad(datei).relative_to(dropbox_basis()).as_posix()


def dokument_id(relativ: str) -> str:
    normalisiert = relativ.replace("\\", "/").casefold()
    return hashlib.sha256(normalisiert.encode("utf-8")).hexdigest()


def relevante_dokumente() -> list[Path]:
    basis = dropbox_basis()
    ergebnis = []
    try:
        for datei in basis.rglob("*"):
            if datei.is_file() and datei.suffix.lower() in config.RELEVANTE_ENDUNGEN:
                try:
                    ergebnis.append(sicherer_pfad(datei))
                except (DokumentPfadFehler, OSError):
                    continue
    except OSError as exc:
        raise DokumentPfadFehler("Dokumentenordner konnte nicht gelesen werden.") from exc
    return sorted(ergebnis, key=lambda p: relativer_pfad(p).casefold())


def finde_dokument(dokument_id_wert: str) -> Path | None:
    if len(dokument_id_wert) != 64 or any(c not in "0123456789abcdef" for c in dokument_id_wert):
        return None
    for datei in relevante_dokumente():
        if dokument_id(relativer_pfad(datei)) == dokument_id_wert:
            return datei
    return None


def metadaten(datei: Path) -> dict:
    datei = sicherer_pfad(datei)
    relativ = relativer_pfad(datei)
    stat = datei.stat()
    teile = Path(relativ).parts
    return {
        "id": dokument_id(relativ),
        "name": datei.name,
        "pfad": relativ,
        "endung": datei.suffix.lower(),
        "ordner": Path(relativ).parent.as_posix() if len(teile) > 1 else "Stammordner",
        "groesse_bytes": stat.st_size,
        "geaendert": stat.st_mtime,
    }
