# AKZENTA AI – Version 0.5

Lokale FastAPI-Anwendung mit read-only Dokumentzugriff auf die konfigurierte
Dropbox und einer persistenten semantischen Wissensbasis in ChromaDB. Embeddings
werden ausschließlich lokal durch Ollama erzeugt; Cloud-Embedding-Dienste kommen
nicht zum Einsatz.

## Installation unter Windows

Voraussetzungen sind Python 3.11 oder neuer und eine lokale Ollama-Installation.

```powershell
cd C:\KI-Projekte\Akzenta-AI
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
ollama pull nomic-embed-text
```

Für `/immobilien-text` wird zusätzlich das bisherige Textmodell benötigt:

```powershell
ollama pull llama3
```

## Konfiguration und Start

```powershell
$env:AKZENTA_DROPBOX_PATH = "C:\Users\S. Vedder\Dropbox\AKZENTA AI"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
$env:OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embed"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8011 --reload
```

Optionale Einstellungen sind `AKZENTA_CHROMA_PATH`,
`AKZENTA_CHROMA_COLLECTION`, `AKZENTA_CHUNK_SIZE` und
`AKZENTA_CHUNK_OVERLAP`. Ohne Änderungen liegt der persistente Index unter
`data/chroma`; in die Dropbox wird niemals geschrieben.

## Wissensbasis-Endpunkte

- `POST /wissensbasis/indexieren` – neue und geänderte Dokumente indexieren,
  unveränderte überspringen und entfernte Dokumente aus ChromaDB löschen
- `GET /wissensbasis/status` – lokaler Indexstatus, Collection, Modell und Zähler
- `GET /wissensbasis/suche?q=Suchtext&limit=5` – semantische Suche mit 1 bis 20 Treffern

Erste Indexierung und Suche:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8011/wissensbasis/indexieren
Invoke-RestMethod http://127.0.0.1:8011/wissensbasis/status
Invoke-RestMethod "http://127.0.0.1:8011/wissensbasis/suche?q=Kapitalanlage&limit=5"
```

Die bestehenden Dokument-Endpunkte bleiben unter `/dokumente` verfügbar,
einschließlich `/dokumente/fehler` und `/dokumente/lesestatus`.

## Tests

Die Tests verwenden temporäre Dokumentbestände, lokale Test-Collections und
Fake-Embeddings. Echte Dropbox- oder Ollama-Zugriffe sind nicht erforderlich.

```powershell
cd C:\KI-Projekte\Akzenta-AI
backend\.venv\Scripts\Activate.ps1
python -m pytest -v
```

## Sicherheit und bekannte Einschränkungen

- Dropbox-Dokumente werden ausschließlich gelesen; ChromaDB schreibt nur in den
  lokalen Projektindex.
- PDFs werden nicht per OCR verarbeitet. Bild-Scans liefern keinen Text.
- Bilder in Präsentationen werden nicht analysiert.
- `python-pptx` kann einzelne PPSX-Dateien je nach OOXML-Inhaltstyp ablehnen.
- Excel-Formeln werden gelesen, aber nicht ausgeführt.
- Der erste Indexlauf benötigt ein laufendes Ollama und das Modell
  `nomic-embed-text`; spätere unveränderte Dokumente werden übersprungen.
- Änderungen am Embedding-Modell erfordern derzeit eine erneute Erstellung des
  Indexordners, da Vektoren verschiedener Modelle nicht gemischt werden dürfen.
- Version 0.5 enthält Indexierung und Suche, aber noch keinen KI-Chat mit Quellen.
  Dieser ist für Version 0.6 vorgesehen.
