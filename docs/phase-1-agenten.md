# Phase 1: sichere Agentenarchitektur

## Umfang

Phase 1 stellt CRM-, E-Mail- und Termin-Agent bereit. CRM erzeugt ausschließlich Änderungsvorschauen, E-Mail ausschließlich Entwürfe und Termine ausschließlich Simulationen. WhatsApp-, Telefon- und Marketing-Agent folgen in späteren Phasen; die Adaptergrenzen für WhatsApp und Telefon sind bereits vorbereitet.

Seit Version 1.4 orchestriert der Agent Manager zusätzlich sichere lokale
Simulationen für WhatsApp, Telefon und Marketing. Die vorhandenen Phase-1-
Endpunkte bleiben kompatibel; es wurden keine externen Provider aktiviert.

Es sind keine Anbieterzugänge hinterlegt. Keine Phase-1-Funktion kann Nachrichten versenden, Termine buchen oder onOffice verändern. Test- und Beispieldaten müssen künstlich sein.

## Sicherheitsmodell

- Zentrale Instanziierung über `AgentManager`.
- Versionierte, UTF-8-kodierte Prompts unter `backend/prompts/<agent>/v1.md`.
- Pydantic-Ein- und Ausgabemodelle mit Größen- und Wertevalidierung.
- Rollen `viewer`, `advisor`, `approver`, `admin`; Vorschauen erfordern mindestens `advisor`.
- Jede Ausgabe enthält Freigabestatus, Request-ID und `external_action_executed=false`.
- Provider sind Mock-Adapter. Deren `execute` blockiert mit `ProviderNotConnected`.
- Das Auditlog enthält nur Agent, Aktion, Actor-ID, Rolle, Request-ID und Ergebnis – keine Anfrageinhalte oder Zugangsdaten. Pfad: `data/agent-audit.jsonl`, konfigurierbar über `AKZENTA_AGENT_AUDIT_LOG`.
- `AKZENTA_AGENT_MOCK_MODE` ist standardmäßig `true`. Ein späteres Umschalten allein aktiviert keine externen Aktionen; dazu sind geprüfte Adapter, bestätigter Zugang und ein separater Freigabefluss erforderlich.

Die Rollenangabe ist in Phase 1 ein validierter Request-Kontext und noch keine produktive Authentifizierung. Vor Provideranbindung muss sie durch serverseitig verifiziertes SSO/IAM ersetzt werden.

## Endpunkte

| Methode | Endpunkt | Verhalten |
|---|---|---|
| GET | `/agents/status` | Status aller Phase-1-Agenten |
| GET | `/agents/crm/status` | onOffice-Mockstatus |
| POST | `/agents/crm/preview` | blockierte CRM-Änderungsvorschau |
| GET | `/agents/email/status` | Gmail-Entwurfsstatus |
| POST | `/agents/email/draft` | E-Mail-Entwurf ohne Versand |
| GET | `/agents/calendar/status` | Google-Calendar-Simulationsstatus |
| POST | `/agents/calendar/simulate` | Terminsimulation ohne Buchung |

Bestehende Endpunkte unter `/dokumente`, `/wissensbasis`, `/chat`, `/immobilien-text` und `/` bleiben erhalten.

## Version 1.7a: Workflow-Core

Der interne Workflow-Core orchestriert mehrere bestehende Agentenfunktionen in einem sicheren Lauf. Er erstellt zuerst eine schreibgeschützte CRM-Vorschau und danach einen E-Mail-Entwurf. Optional ergänzt er eine Kalendersimulation, wenn `simulate_calendar=true` und `preferred_start` gesetzt ist.

Der Workflow-Core besitzt keinen externen Provider und führt keine externen Aktionen aus: Er sendet keine E-Mail, erstellt keinen Kalendertermin und verändert keine CRM-Daten. Alle Schrittergebnisse weisen `external_action_executed=false` aus; auch der gesamte Workflow meldet diesen sicheren Zustand.

| Methode | Endpunkt | Verhalten |
|---|---|---|
| GET | `/agents/workflows/status` | Sicherer interner Status und Fähigkeiten des Workflow-Core |
| POST | `/agents/workflows/core/run` | CRM-Vorschau, E-Mail-Entwurf und optionale Kalendersimulation |

Beispielrequest:

```json
{
  "lead_id": "LEAD-170",
  "recipient_name": "Testperson",
  "target_group": "buyer",
  "purpose": "Abstimmung zum weiteren Ablauf",
  "simulate_calendar": true,
  "preferred_start": "2026-07-20T10:00:00+02:00",
  "duration_minutes": 45,
  "timezone": "Europe/Berlin"
}
```

Ist die Kalendersimulation aktiviert, aber `preferred_start` fehlt, wird die Anfrage mit HTTP 422 abgewiesen. Ohne aktivierte Kalendersimulation werden ausschließlich CRM-Vorschau und E-Mail-Entwurf erzeugt.

## Version 1.7b: Human-in-the-Loop-Freigaben

Jeder erfolgreiche Workflow erhält eine eindeutige `workflow_id`, wird prozesslokal registriert und mit einem SHA-256-Fingerprint über ID, vorbereitete Schritte und Sicherheitsfelder geschützt. Der Ablauf ist: Workflow vorbereiten, Freigabe anfordern, als Mensch genehmigen oder ablehnen und eine genehmigte Fassung einmalig simuliert ausführen.

Status sind `pending`, `approved`, `rejected`, `expired` und `executed`. Nur `pending` kann entschieden werden. Nur eine gültige, nicht abgelaufene `approved`-Freigabe mit unverändertem Workflow-Fingerprint kann ausgeführt werden. Ablehnung, Ablauf, Manipulation und Mehrfachausführung werden blockiert.

| Methode | Endpunkt | Verhalten |
|---|---|---|
| GET | `/agents/approvals/status` | Simulationsmodus, Speicher- und Sicherheitsgrenzen |
| POST | `/agents/approvals` | Freigabe für eine vorhandene `workflow_id` anlegen |
| GET | `/agents/approvals/{approval_id}` | Aktuellen Status lesen |
| POST | `/agents/approvals/{approval_id}/decision` | Ausstehende Freigabe genehmigen oder ablehnen |
| POST | `/agents/approvals/{approval_id}/execute` | Genehmigte Schritte einmalig lokal simulieren |

Beispielablauf (Responses gekürzt):

```http
POST /agents/workflows/core/run
{"lead_id":"LEAD-170","recipient_name":"Testperson","target_group":"buyer","purpose":"Weiterer Ablauf"}
-> {"workflow_id":"wf_...","approval_required":true,"approval_status":"pending","external_action_executed":false}

POST /agents/approvals
{"workflow_id":"wf_...","expires_in_minutes":30,"requested_by":"steli"}
-> {"approval_id":"apr_...","status":"pending","workflow_fingerprint":"..."}

POST /agents/approvals/apr_.../decision
{"decision":"approved","decided_by":"steli","reason":"Entwurf geprüft"}
-> {"approval_id":"apr_...","status":"approved"}

POST /agents/approvals/apr_.../execute
-> {"status":"executed","execution_mode":"simulation","external_actions_performed":false,"safe":true}
```

Der Speicher ist absichtlich nur In-Memory, thread-sicher und nicht persistent: Bei Prozessneustart gehen vorbereitete Workflows und Freigaben verloren; mehrere Serverprozesse teilen den Zustand nicht. Es gibt keine Datenbankmigration und keinen externen Connector. Version 1.7b versendet auch nach Freigabe keine E-Mail, erstellt keinen Kalendertermin und ändert keine CRM-Daten. Eine Freigabe erlaubt ausschließlich die Markierung einer lokalen Simulation als ausgeführt.

## Version 1.7c: persistente Workflow-Engine

Version 1.7c ersetzt die prozesslokalen Dictionaries durch eine SQLite-Repository-Schicht aus der Python-Standardbibliothek. Standardmäßig liegt die Datenbank unter `data/workflow_engine.sqlite3`; `AKZENTA_WORKFLOW_DB` kann einen anderen Pfad vorgeben. Tests injizieren stets eine temporäre Datenbank. SQLite-Verbindungen werden pro Operation geöffnet, Foreign Keys und WAL-Modus aktiviert und zusammengehörige Status- und Auditänderungen in Transaktionen gespeichert.

Das Schema Version 1 umfasst `workflows`, `approvals`, `audit_events` und `schema_version`. Gespeichert werden Workflow-Anfrage und vollständige Antwort als stabiles UTF-8-JSON, SHA-256-Fingerprint, Status und Ausführungszeitpunkte sowie Freigabeentscheidungen, Ablaufzeiten und die chronologische Historie. Die Initialisierung ist idempotent, überschreibt keine Bestandsdaten und bricht bei einer unbekannten neueren Schema-Version sicher ab. Damit bleiben vorbereitete, genehmigte, abgelehnte, abgelaufene und bereits simuliert ausgeführte Vorgänge nach einer Neuinitialisierung der Services erhalten.

Neue Lese-Endpunkte:

| Methode | Endpunkt | Verhalten |
|---|---|---|
| GET | `/agents/workflows` | Neueste Workflows, optional nach Status, maximal 100 |
| GET | `/agents/workflows/{workflow_id}` | Persistierter Workflow mit vorbereiteten Schritten |
| GET | `/agents/workflows/{workflow_id}/audit` | Unveränderbare chronologische Workflow-Historie |
| GET | `/agents/approvals` | Freigaben, optional nach Workflow oder Status, maximal 100 |

Das Audit-Log erfasst unter anderem `workflow_created`, `approval_created`, Genehmigung oder Ablehnung, Ablauf, blockierte Ausführungen, Integritätsfehler sowie Start und Abschluss einer Simulation. Es enthält nur notwendige Akteure, Status und knappe Gründe, keine Zugangsdaten. Der Fingerprint wird aus stabil serialisierten sicherheitsrelevanten Workflow-Daten berechnet und unmittelbar vor Ausführung erneut geprüft. Ein bedingtes SQLite-Update von `approved` nach `executed` verhindert doppelte oder parallele Ausführung.

Beispielablauf:

1. Workflow über `POST /agents/workflows/core/run` vorbereiten und dauerhaft speichern.
2. Approval über `POST /agents/approvals` erstellen.
3. Server oder Services mit demselben Datenbankpfad neu initialisieren.
4. Approval weiterhin über `GET /agents/approvals/{approval_id}` abrufen.
5. Approval genehmigen.
6. Genehmigten Workflow genau einmal lokal simulieren.
7. Historie über `GET /agents/workflows/{workflow_id}/audit` abrufen.

Sicherheitsgrenzen und bekannte Grenzen: Persistenz bedeutet keine automatische externe Ausführung. Auch Version 1.7c sendet keine E-Mail, erstellt keinen Kalendertermin und verändert keine CRM-Daten; `external_actions_performed` bleibt immer `false`. SQLite eignet sich für die lokale Einzelinstanz. Für einen späteren verteilten Betrieb mit mehreren Servern kann PostgreSQL erforderlich werden. Rollen im Request sind weiterhin keine produktive Authentifizierung, und Audit-Ereignisse sind über die API weder änderbar noch löschbar.

## Fehlerbehandlung

- Pydantic-Validierungsfehler: HTTP 422.
- Unzureichende Rolle: HTTP 403.
- Unerwartete interne Fehler: HTTP 500 ohne interne Details oder Pfade.
- Nicht verbundener Anbieter: Adapter blockiert jede Ausführung.

## Tests

```powershell
& 'C:\Users\S. Vedder\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests -q --basetemp '.tmp\phase1-final'
cd frontend
npm.cmd test -- --run
npm.cmd run build
```

Das explizite Testverzeichnis verhindert, dass lokale, nicht lesbare Hilfsordner wie `pytest-temp` von Pytest eingesammelt werden. Die defekte lokale `backend/.venv` muss separat mit einer verfügbaren Python-3.11+-Installation neu erstellt werden.
