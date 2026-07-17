# AKZENTA AI – Version 0.6

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
$env:OLLAMA_CHAT_MODEL = "llama3"
$env:OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
$env:OLLAMA_REQUEST_TIMEOUT = "180"
$env:CHAT_MAX_CONTEXT_CHARS = "12000"
$env:CHAT_MIN_RELEVANCE = "0.25"
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

## Lokaler Dokumentenchat

- `POST /chat/dokumente` – beantwortet eine Frage ausschließlich aus relevanten
  Abschnitten der lokalen Wissensbasis und liefert die tatsächlich zitierten Quellen
- `GET /chat/status` – prüft Ollama, Chat- und Embedding-Modell, ChromaDB und Index

PowerShell-Beispiele:

```powershell
$body = @{
    frage = "Welche Vorteile bietet eine Immobilie als Kapitalanlage?"
    limit = 5
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri http://127.0.0.1:8011/chat/dokumente `
    -ContentType "application/json; charset=utf-8" `
    -Body $body

Invoke-RestMethod http://127.0.0.1:8011/chat/status
```

Antworten nennen verwendete Dokumentstellen mit `[Quelle 1]`, `[Quelle 2]` usw.
Nicht belegbare Fragen werden ausdrücklich als nicht eindeutig in der
AKZENTA-Wissensbasis auffindbar beantwortet. Dokumentinhalte gelten als nicht
vertrauenswürdige Daten; darin enthaltene Anweisungen werden nicht befolgt.

## Tests

Die Tests verwenden temporäre Dokumentbestände, lokale Test-Collections und
Fake-Embeddings. Echte Dropbox- oder Ollama-Zugriffe sind nicht erforderlich.

```powershell
cd C:\KI-Projekte\Akzenta-AI
backend\.venv\Scripts\Activate.ps1
python -m pytest -v
```

## Datenschutz, Sicherheit und bekannte Einschränkungen

- Dropbox-Dokumente werden ausschließlich gelesen; ChromaDB schreibt nur in den
  lokalen Projektindex.
- Dokumenttexte, Fragen, Embeddings und Antworten bleiben lokal. Es werden keine
  Cloud-APIs von OpenAI, Anthropic oder anderen Anbietern verwendet.
- Quellen werden nur ausgegeben, wenn das lokale Modell sie tatsächlich in der
  Antwort zitiert. Ungültige Quellenmarker werden entfernt.
- PDFs werden nicht per OCR verarbeitet. Bild-Scans liefern keinen Text.
- Bilder in Präsentationen werden nicht analysiert.
- `python-pptx` kann einzelne PPSX-Dateien je nach OOXML-Inhaltstyp ablehnen.
- Excel-Formeln werden gelesen, aber nicht ausgeführt.
- Der erste Indexlauf benötigt ein laufendes Ollama und das Modell
  `nomic-embed-text`; spätere unveränderte Dokumente werden übersprungen.
- Änderungen am Embedding-Modell erfordern derzeit eine erneute Erstellung des
  Indexordners, da Vektoren verschiedener Modelle nicht gemischt werden dürfen.
- Die Relevanzschwelle ist eine vorsichtige Heuristik. Fachlich ähnliche, aber
  sprachlich weit entfernte Dokumentstellen können übersehen werden.
- Prompt-Injection wird durch Systemregeln, Datengrenzen und Ausgabefilter
  reduziert, kann bei lokalen Sprachmodellen aber nicht mathematisch garantiert
  ausgeschlossen werden.
