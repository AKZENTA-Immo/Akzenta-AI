export interface BackendInfo {
  status: string
  branche: string
  version: string
}

export interface ChatRequest {
  frage: string
  limit?: number
}

export interface ChatSource {
  quellen_nummer: number
  dokument_id: string
  dateiname: string
  relativer_pfad: string
  abschnitt: number
  seite?: number | null
  folie?: number | null
  tabellenblatt?: string | null
  relevanz: number
  textausschnitt: string
}

export interface ChatResponse {
  frage: string
  antwort: string
  quellen?: ChatSource[]
  verwendetes_chat_modell?: string
  verwendetes_embedding_modell?: string
  dauer_sekunden?: number
}

export interface ChatStatus {
  ollama_erreichbar: boolean
  chat_modell_verfuegbar: boolean
  chat_modell: string
  embedding_modell: string
  chromadb_erreichbar: boolean
  indexierte_dokumente: number
  gespeicherte_abschnitte: number
  chat_bereit: boolean
  fehlermeldung?: string | null
}

export interface KnowledgeStatus {
  chromadb_erreichbar: boolean
  collection_name: string
  indexierte_dokumente: number
  gespeicherte_abschnitte: number
  embedding_modell: string
  speicherort: string
  letzte_indexierung?: string | null
}

export interface IndexingError {
  pfad: string
  ursache: string
}

export interface IndexingResponse {
  status: string
  dokumente_gesamt: number
  neu_indexiert: number
  aktualisiert: number
  unveraendert: number
  entfernt: number
  fehlerhaft: number
  abschnitte_gesamt: number
  dauer_sekunden: number
  fehler?: IndexingError[]
}

export type ReadStatus = '' | 'lesbar' | 'fehlerhaft'
export type IndexStatus = '' | 'indexiert' | 'nicht_indexiert'
export type DocumentSort = 'dateiname' | 'dateityp' | 'dateigroesse' | 'geaendert_am' | 'relativer_pfad'
export interface DocumentFilters { suche: string; dateityp: string; hauptordner: string; lesestatus: ReadStatus; indexstatus: IndexStatus; sortierung: DocumentSort; sortierreihenfolge: 'asc' | 'desc'; limit: number; offset: number }
export interface DocumentSummary { dokument_id: string; dateiname: string; dateiendung: string; relativer_pfad: string; hauptordner: string; dateigroesse_bytes: number; geaendert_am: string; lesbar: boolean; lesefehler?: string | null; indexiert: boolean; abschnitt_anzahl: number; seiten_oder_elemente?: number | null; mime_typ?: string | null }
export interface DocumentListResponse { gesamt: number; limit: number; offset: number; dokumente: DocumentSummary[] }
export interface DocumentDetails extends DocumentSummary { textauszug: string; abschnittsmetadaten: Record<string, unknown> }
export interface DocumentSection { abschnitt_id: string; text: string; seite?: number | null; folie?: number | null; tabellenblatt?: string | null; abschnittsnummer: number; zeichenanzahl: number; metadaten: Record<string, string | number | boolean | null> }
export interface DocumentSectionsResponse { gesamt: number; limit: number; offset: number; abschnitte: DocumentSection[] }
export interface DocumentStatistics { gesamt: number; nach_dateityp: Record<string, number>; nach_hauptordner: Record<string, number>; lesbar: number; fehlerhaft: number; indexiert: number; nicht_indexiert: number; gesamtgroesse_bytes: number; abschnitte_gesamt: number }
export type AgentKind = 'crm' | 'email' | 'calendar'
export interface AgentStatus { agent: AgentKind; mode: 'mock' | 'draft' | 'simulation' | 'connected'; provider: string; provider_connected: boolean; external_actions_enabled: boolean; prompt_version: string; capabilities: string[] }
export interface AgentResponse { request_id: string; agent: AgentKind; status: 'draft' | 'simulation' | 'blocked'; summary: string; output: Record<string, unknown>; approval: { required: boolean; approved: boolean; approval_id: string; reason: string }; external_action_executed: boolean; created_at: string }
export type AgentManagerTarget = 'crm' | 'email' | 'kalender' | 'whatsapp' | 'telefon' | 'marketing' | 'dokumente' | 'immobilien_text' | 'allgemein'
export interface AgentManagerResponse { agent: AgentManagerTarget; confidence: number; reason: string; original_message: string; simulation: boolean; uncertain: boolean; result: { status: string; external_action_executed: boolean } }
export interface AgentExecutionResponse { agent: AgentManagerTarget; intent: string; confidence: number; reasoning: string; simulation: boolean; approval_required: boolean; status: 'simulated' | 'blocked' | 'error'; result: Record<string, unknown>; missing_information: string[]; proposed_actions: string[]; warnings: string[]; uncertain: boolean }
export interface OnOfficeStatus { enabled: boolean; mode: string; configured: boolean; reachable: boolean; authenticated: boolean; api_url: string; permissions_checked: boolean; last_check?: string | null; error_code?: string | null; error_message?: string | null }
