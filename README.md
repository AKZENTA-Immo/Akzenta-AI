# AKZENTA AI – Version 0.4

Lokale FastAPI-Anwendung für ein Immobilienmaklerunternehmen in Hamburg. Die
konfigurierte Dropbox-Wissensbasis wird ausschließlich gelesen. Unterstützt
werden PDF, DOCX, XLSX, TXT, PPTX und PPSX.

## Installation und Start (PowerShell)

Voraussetzung ist Python 3.11 oder neuer.

```powershell
cd C:\KI-Projekte\Akzenta-AI
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:AKZENTA_DROPBOX_PATH = "C:\Users\S. Vedder\Dropbox\AKZENTA AI"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
```

Ohne Aktivierung der virtuellen Umgebung kann jeweils
`backend\.venv\Scripts\python.exe` anstelle von `python` verwendet werden.

Ollama ist für `/immobilien-text` erforderlich und kann über `OLLAMA_URL` und
`OLLAMA_MODEL` konfiguriert werden. Die Dokument-Endpunkte benötigen Ollama nicht.

## Dokument-Endpunkte

- `GET /dokumente` – gefilterte Dokumentliste mit stabilen IDs und relativen Pfaden
- `GET /dokumente/statistik` – Verteilung nach Dateityp und Hauptordner
- `GET /dokumente/lesestatus` – erfolgreiche und fehlerhafte Leseversuche je Dateityp
- `GET /dokumente/{dokument_id}` – Metadaten und höchstens 3.000 Zeichen Vorschau
- `GET /dokumente/{dokument_id}/text` – vollständig extrahierter Text

Beispiele:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/dokumente
Invoke-RestMethod http://127.0.0.1:8010/dokumente/statistik
Invoke-RestMethod http://127.0.0.1:8010/dokumente/lesestatus
```

## Tests

```powershell
cd C:\KI-Projekte\Akzenta-AI
python -m pytest -v
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

Danach kann der lokale Smoke-Test beispielsweise mit
`Invoke-RestMethod http://127.0.0.1:8010/` ausgeführt werden.

## Sicherheit und Einschränkungen

Dateien werden unmittelbar vor dem Lesen auf ihren aufgelösten Pfad innerhalb
von `AKZENTA_DROPBOX_PATH` und auf eine erlaubte Endung geprüft. Die API nimmt
keine Dateipfade entgegen und gibt nur relative Dropbox-Pfade aus. Der Leser
öffnet Dokumente nur lesend; Excel-Formeln werden als Text gelesen und weder
berechnet noch verändert.

PDFs werden nicht per OCR verarbeitet, weshalb Bild-Scans keinen Text liefern.
Bilder in Präsentationen werden nicht analysiert. Verschlüsselte, beschädigte
oder von den Bibliotheken nicht unterstützte Dokumente werden als fehlerhaft
gemeldet. `/dokumente/lesestatus` liest sämtliche relevanten Dokumente und kann
bei großen Wissensbasen entsprechend dauern.
