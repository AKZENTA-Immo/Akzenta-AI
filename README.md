# AKZENTA AI

Lokale FastAPI-Anwendung für ein Immobilienmaklerunternehmen in Hamburg. Die
Dropbox-Wissensbasis wird ausschließlich gelesen.

## Voraussetzungen unter Windows

- Python 3.11 oder neuer
- Ollama auf `http://localhost:11434`
- Ollama-Modell `llama3`
- Leserechte für `C:\Users\S. Vedder\Dropbox\AKZENTA AI`

## Installation und Start (PowerShell)

```powershell
cd C:\KI-Projekte\Akzenta-AI
py -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
```

Falls PowerShell die Aktivierung blockiert, kann die Anwendung ohne Aktivierung
gestartet werden:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
```

Ollama bei Bedarf in einem zweiten Fenster starten:

```powershell
ollama serve
ollama pull llama3
```

## Endpunkte testen

Im Browser steht die interaktive Dokumentation unter
`http://127.0.0.1:8010/docs` bereit. Alternativ in PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/
Invoke-RestMethod http://127.0.0.1:8010/dokumente
Invoke-RestMethod http://127.0.0.1:8010/dokumente/statistik
Invoke-RestMethod http://127.0.0.1:8010/immobilien-text
```

`/dokumente` berücksichtigt nur `.pdf`, `.docx`, `.xlsx`, `.txt`, `.pptx` und
`.ppsx`. Bilder, Videos sowie PSD- und BMP-Dateien werden dadurch ignoriert.
`/dokumente/statistik` liefert die Gesamtzahl sowie Zählungen nach Dateiendung
und dem ersten Ordner unterhalb der Wissensbasis. Dateien direkt im Stammordner
werden unter `Stammordner` gezählt.

## Konfiguration

Die Standardwerte können vor dem Start über Umgebungsvariablen geändert werden:

```powershell
$env:AKZENTA_DROPBOX_PATH = "C:\Users\S. Vedder\Dropbox\AKZENTA AI"
$env:OLLAMA_URL = "http://localhost:11434/api/generate"
$env:OLLAMA_MODEL = "llama3"
```
