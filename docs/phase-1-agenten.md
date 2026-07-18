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
