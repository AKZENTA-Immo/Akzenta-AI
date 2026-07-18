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
## Version 1.8 – mehrstufiger Workflow-Orchestrator

Version 1.8 erweitert den persistenten Workflow-Core um einen zustandsbehafteten `WorkflowOrchestrator`. Definitionen und Aktionen sind intern registriert; Requests können weder Python-Code noch Funktionsnamen, Imports, Shell-Befehle oder Bedingungen zur freien Ausführung liefern. `eval` wird nicht verwendet.

Die Definition `lead_qualification` umfasst `validate_lead`, `crm_lookup`, `document_check`, `email_draft`, `calendar_preview`, `approval_gate`, `simulated_execution` und `finalize`. `seller_follow_up` umfasst `validate_request`, `crm_lookup`, `market_context_preview`, `email_draft`, `approval_gate`, `simulated_execution` und `finalize`.

Workflow-Zustände sind `created`, `running`, `waiting_for_approval`, `paused`, `completed`, `failed` und `cancelled`. Schritte verwenden `pending`, `running`, `completed`, `failed`, `skipped`, `waiting` und `blocked`. Abgeschlossene Schritte werden bei Resume nicht erneut ausgeführt; abgebrochene Workflows bleiben endgültig gesperrt. Fehlgeschlagene Schritte können ausschließlich kontrolliert und innerhalb von `max_retries` erneut versucht werden.

Sichere Bedingungen unterstützen nur `always`, `input_present`, `input_equals`, `previous_step_succeeded` und `previous_step_output_present`. So wird etwa `calendar_preview` ohne Terminwunsch deterministisch als `skipped` markiert. Abhängigkeiten, unbekannte Schritte, doppelte IDs und Zyklen werden validiert.

Das Approval-Gate nutzt unverändert den vorhandenen `ApprovalService`. Es speichert Approval-ID und Workflow-Fingerprint persistent, setzt Schritt und Workflow wartend und blockiert alle Folgeschritte. Nur `approved` oder `executed` erlaubt Resume; `pending`, `rejected`, `expired` und Fingerprint-Manipulation blockieren. Eine Freigabe erlaubt ausschließlich die Fortsetzung der Simulation.

SQLite-Schema 2 ergänzt additiv `workflow_definitions`, `workflow_instances` und `workflow_steps`; Daten aus Schema 1 bleiben erhalten. Foreign Keys, WAL, Transaktionen und bedingte Statusupdates bleiben aktiv. SQLite ist weiterhin für eine lokale Einzelinstanz ausgelegt. Audit-Ereignisse umfassen Erzeugung, Start, Schrittstart/-abschluss/-fehler/-skip, Approval-Wartezustand, Resume, Retry, Abbruch, Blockierung und Abschluss.

Neue Endpunkte:

- `GET /agents/workflow-engine/status`
- `GET /agents/workflow-definitions` und `GET /agents/workflow-definitions/{definition_id}`
- `POST /agents/workflows/start`
- `POST /agents/workflows/{workflow_id}/run`, `/resume`, `/retry` und `/cancel`
- `GET /agents/workflows/{workflow_id}/steps`

Beispielablauf: Workflow über `/agents/workflows/start` mit `definition_id=lead_qualification` starten, über `/run` bis zum Approval-Gate ausführen, die verknüpfte Freigabe über `/agents/approvals/{approval_id}` abrufen und über `/decision` freigeben. Anschließend `/resume` aufrufen, den Abschluss über `/agents/workflows/{workflow_id}` prüfen und die Historie über `/agents/workflows/{workflow_id}/audit` abrufen.

Version 1.8 führt keine echten externen Aktionen aus: keine E-Mail, kein Kalendertermin, keine CRM-Schreiboperation, kein WhatsApp und keine Telefonie. Alle Schritt- und Workflow-Ausgaben garantieren `safe=true`, `execution_mode=simulation` und `external_actions_performed=false`.

## Version 1.9 – lokale RAG Knowledge Engine

`backend/rag` indexiert die vorhandene Dropbox-Wissensbasis lokal. Loader, Chunker, Ollama-Embedding-Adapter, SQLite-Vektorspeicher, Retriever und `KnowledgeService` sind getrennt testbar. Das additive SQLite-Schema umfasst `documents`, `chunks` und `embeddings`; Quellmetadaten enthalten Dateiname, relativen Pfad, Seite beziehungsweise Folie, Abschnitt, Ordner, Dokumenttyp und Änderungsdatum. Quelldateien werden nie verändert.

Die semantische Suche liefert Top-K-Treffer mit Cosine-Score und echten Quellen. `/knowledge/ask` übergibt ausschließlich gefundene Chunks an das lokale Ollama-Chatmodell. Ohne ausreichend relevanten Kontext lautet die Antwort exakt `Keine passende Information gefunden.` Quellen erscheinen nur, wenn die Modellantwort sie tatsächlich referenziert.

Der Workflow-Orchestrator kennt die allowlist-geschützte Aktion `knowledge_lookup`. Sie wird nur bei vorhandenem `knowledge_query` ausgeführt und verändert keine externen Systeme. CRM-, E-Mail-, Telefon- und Marketing-Agent deklarieren denselben lokalen Lesezugriff als Capability.
# Phone Agent – lokale Gesprächssteuerung

Der `CallManager` koordiniert Gesprächszustand, Dialog, Termin, Eskalation und Nachbereitung. `ConversationMemory` hält Name, Telefon, Objekt, Interesse, Budget, Termin und Notizen über mehrere Nachrichten und persistiert sie in den Tabellen `calls`, `call_messages`, `call_summary` und `phone_sessions`. Termine liegen vorläufig providerneutral in der lokalen Tabelle `appointments`.

Die Intent-Erkennung umfasst Begrüßung, Rückruf, Verkäufer, Kapitalanlage, Besichtigung, Termin, Dokumente, Preis, Objektfrage, Finanzierung, Ablehnung, Verabschiedung und Unbekannt. Beschwerden, Konflikte, rechtliche Fragen, technische Probleme, Unsicherheit oder der ausdrückliche Wunsch nach einem Mitarbeiter lösen eine Übergabe aus.

Jeder Anruf startet die Workflow-Definition `phone_conversation`. Sie registriert die Actions `phone_call`, `appointment_booking`, `email_followup`, `crm_update`, `knowledge_lookup` und `handover`. CRM-Schreibzugriffe bleiben Vorschauen, Follow-up-Mails bleiben Entwürfe und Termine bleiben lokale Reservierungen. Alle Komponenten sind über Konstruktor-Injektion austauschbar.
# Operator Dashboard 2.1

Das Dashboard-Modul trennt Conversation-, Workflow- und Lead-Monitor, Statistik, Agentenstatus und Event-Persistenz. `DashboardService` aggregiert diese injizierten, testbaren Lesedienste für das Overview. Der API-Router enthält ausschließlich GET-Routen.

Datenfluss: Phone-Agent-SQLite → Conversation/Lead Monitor; Workflow-Repository-SQLite → Workflow Monitor; vorhandene Quellenmetadaten → Knowledge Panel; beide Pfade → Statistik/Overview → REST beziehungsweise SSE → React-Dashboard. Es gibt kein paralleles Telefon-, CRM- oder Workflow-System.

`dashboard_events` speichert unveränderliche Hinweise mit Typ, Severity, Entitätsbezug, JSON-Metadaten und Zeitstempel. `dashboard_notifications` speichert die lesbare Benachrichtigungsprojektion. Beide Tabellen werden mit `CREATE TABLE IF NOT EXISTS` additiv angelegt. Der SSE-Dienst pollt austauschbar, sendet nur neue Events und Keepalives und behandelt Client-Abbruch durch Generator-Cancellation.

Agentenstatus kennt `running`, `idle`, `degraded`, `unavailable` und `error`. Phone Agent, CRM Agent, Email Agent, Marketing Agent, Workflow Engine, Knowledge Engine, Ollama und SQLite werden lokal bewertet; Ollama wird dafür nicht eigens aufgerufen.

Sicherheitsgrenzen: keine Dashboard-Endpunkte zum Ändern oder Löschen, kein Starten von Workflows, keine Übernahme von Gesprächen, kein Versand und keine CRM-Änderung. Es werden weder Audio noch Secrets ausgegeben. Suche verwendet ausschließlich gebundene SQL-Parameter.

# Conversation Engine 2.2 – Persistenzkern

Die Conversation Engine verwendet eine eigene SQLite-Datenbank (`AKZENTA_CONVERSATION_DB`) und versionierte, idempotente Migrationen. Schema-Version 1 legt `conversations`, `participants`, `messages`, `events`, `attachments`, `tags`, `message_links`, `conversation_state` und `conversation_memory` an. Eine unbekannte neuere Schema-Version wird sicher abgelehnt.

`ConversationRepository` kapselt sämtliche SQL-Zugriffe, aktiviert Fremdschlüssel und WAL und nutzt gebundene Parameter. Teilnehmeridentitäten sind für Telefon, Mobiltelefon, E-Mail, CRM und onOffice indexiert. Anhänge werden über Inhalts-Hash beziehungsweise vorhandene Dokument-ID global dedupliziert; `message_links` referenziert dieselbe Anlage oder dasselbe RAG-Dokument aus beliebig vielen Nachrichten, ohne Dokumentinhalte erneut zu speichern.
