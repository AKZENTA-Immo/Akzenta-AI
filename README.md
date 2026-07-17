# AKZENTA AI – Version 0.8

Lokale FastAPI-Anwendung mit read-only Dokumentzugriff auf die konfigurierte
Dropbox und einer persistenten semantischen Wissensbasis in ChromaDB. Embeddings
werden ausschließlich lokal durch Ollama erzeugt; Cloud-Embedding-Dienste kommen
nicht zum Einsatz.

Version 0.8 ergänzt das Corporate Design um ein professionelles Dokumentencenter.
Es zeigt den ausschließlich lesbaren Bestand mit Statistik, serverseitiger
Pagination, Suche und Filtern sowie sicheren Metadaten-, Text- und
Abschnittsvorschauen. Dokumentenchat und Wissensbasis bleiben unverändert verfügbar.

## Dokumentencenter

Der Navigationspunkt **Dokumente** öffnet die responsive Dokumentenübersicht.
Durchsucht werden Dateiname, relativer Pfad, Hauptordner und Dateiendung. Diese
Dateilistensuche ist bewusst von der semantischen Inhaltssuche unter
`/wissensbasis/suche` getrennt. Filter stehen für Dateityp, Hauptordner,
Lesestatus und Indexstatus bereit; sortiert werden kann nach Name, Typ, Größe,
Änderungsdatum und relativem Pfad.

- `GET /dokumente` – Suche, Filter, Sortierung und Pagination (`limit` maximal 100)
- `GET /dokumente/{dokument_id}` – sichere Metadaten und begrenzter Textauszug
- `GET /dokumente/{dokument_id}/abschnitte` – paginierte Indexabschnitte
- `GET /dokumente/statistik` – Typen, Ordner, Status, Größe und Abschnitte

Es gibt keinen Download-, Lösch-, Umbenennungs- oder Verschiebe-Endpunkt.
Absolute Windows-Pfade werden nicht ausgegeben. Die Vorschau rendert Text ohne
HTML-Ausführung; PDF-/Office-Rendering und OCR sind für spätere Versionen vorgesehen.

## Architektur

- `backend`: FastAPI, Dokumentleser, Ollama, ChromaDB und Dokumentenchat
- `frontend`: React 19, TypeScript im Strict Mode, Vite und zentrale Fetch-API
- `data/chroma`: ausschließlich lokaler, persistenter Vektorindex
- Dropbox: nur lesbare Quelldokumente; niemals Ziel für Anwendungsdaten

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
$env:AKZENTA_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
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

Nach dem Update auf 0.6.1 sollte der bestehende Index einmal vollständig und
sicher neu aufgebaut werden. Dabei wird ausschließlich `data/chroma` ersetzt;
die Dropbox bleibt unverändert:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8011/wissensbasis/indexieren?vollstaendig=true"
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

Für korrekte Umlaute und Sonderzeichen in Windows PowerShell empfiehlt sich vor
den API-Aufrufen:

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
# Optional in älteren Konsolen:
chcp 65001
```

Diese Einstellung verbessert nur die Konsolendarstellung. Bereits fehlerhaft
gespeicherte Indextexte werden dadurch nicht repariert; dafür ist der oben
beschriebene vollständige Reindex erforderlich.

## Weboberfläche starten

In einem zweiten PowerShell-Fenster:

```powershell
cd C:\KI-Projekte\Akzenta-AI\frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8011"
npm install
npm run dev
```

Danach ist die Oberfläche unter `http://127.0.0.1:5173` erreichbar. Falls die
PowerShell-Ausführungsrichtlinie `npm.ps1` blockiert, können dieselben Befehle
mit `npm.cmd` ausgeführt werden.

Die Oberfläche besteht aus einer anthrazitfarbenen linken Navigation und einem
hellen Arbeitsbereich. Die Chat-Seite bietet Beispielfragen, ein großes
Eingabefeld, sicher gerenderte Markdown-Antworten und kompakte, aufklappbare
Quellenkarten. Die Wissensbasis-Seite zeigt farblich unterscheidbare
Systemzustände, Indexdetails und das Ergebnis einer manuell gestarteten
Aktualisierung. Das Layout passt sich Tablet- und Smartphonebreiten an.

### CORS

Das Backend erlaubt standardmäßig ausschließlich die lokalen Frontend-Ursprünge
`http://localhost:5173` und `http://127.0.0.1:5173`. Weitere lokale Ursprünge
können kommasepariert gesetzt werden:

```powershell
$env:AKZENTA_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
```

Es wird bewusst keine globale `*`-Freigabe verwendet.

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

Frontend-Tests und Produktions-Build:

```powershell
cd C:\KI-Projekte\Akzenta-AI\frontend
npm test
npm run build
npm audit
```

## Fehlerbehebung

- **Backend nicht erreichbar:** Prüfen, ob Uvicorn auf Port 8011 läuft und
  `VITE_API_BASE_URL` korrekt gesetzt wurde.
- **Chat nicht bereit:** `GET /chat/status` prüfen und bei Bedarf
  `ollama pull llama3` sowie `ollama pull nomic-embed-text` ausführen.
- **Wissensbasis leer:** In der Weboberfläche „Wissensbasis aktualisieren“
  wählen oder `POST /wissensbasis/indexieren` aufrufen.
- **Browser meldet CORS:** Den exakten lokalen Frontend-Ursprung in
  `AKZENTA_ALLOWED_ORIGINS` ergänzen und das Backend neu starten.
- **Anfrage dauert lange:** Lokale Modellantworten können je nach Hardware
  mehrere Minuten benötigen. Das Frontend zeigt währenddessen einen Ladezustand.

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
- Das Dokumentencenter ist eine sichere Text-/Metadatenansicht; native PDF- und
  Office-Vorschau sowie OCR folgen in späteren Versionen.
- Chatverläufe werden nicht dauerhaft im Browser gespeichert. Ein Neuladen der
  Seite verwirft die aktuell angezeigte Antwort.
