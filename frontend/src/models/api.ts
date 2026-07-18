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
export type AgentManagerTarget = 'crm' | 'email' | 'kalender' | 'whatsapp' | 'telefon' | 'marketing' | 'dokumente' | 'immobilien' | 'allgemein'
export interface AgentManagerResponse { agent: AgentManagerTarget; display_name: string; action: string; confidence: number; reason: string; original_message: string; simulation: boolean; uncertain: boolean; secondary_agents: string[]; result: { status: string; external_action_executed: boolean } }
export interface AgentExecutionResponse { agent: AgentManagerTarget; display_name: string; action: string; intent: string; confidence: number; reason: string; reasoning: string; simulation: boolean; approval_required: boolean; requires_confirmation: boolean; status: 'simulated' | 'blocked' | 'error' | 'confirmation_required' | 'not_supported' | 'validation_error' | 'rejected'; result: Record<string, unknown>; missing_information: string[]; proposed_actions: string[]; warnings: string[]; uncertain: boolean; secondary_agents: string[]; error?: string | null; metadata: Record<string, unknown> }
export interface OnOfficeStatus { enabled: boolean; mode: string; configured: boolean; reachable: boolean; authenticated: boolean; api_url: string; permissions_checked: boolean; last_check?: string | null; error_code?: string | null; error_message?: string | null }
export interface DashboardAgentStatus { name:string; status:'running'|'idle'|'degraded'|'unavailable'|'error'; checked_at:string; message:string; error_details?:string|null }
export interface DashboardEvent { id:string; event_type:string; severity:'info'|'warning'|'error'|'critical'; title:string; message:string; entity_type?:string|null; entity_id?:string|null; created_at:string }
export interface DashboardOverview { active_conversations:number; conversations_today:number; open_escalations:number; open_appointments:number; prepared_followups:number; active_workflows:number; failed_workflows:number; new_leads:number; average_lead_score:number; agent_statuses:DashboardAgentStatus[]; recent_events:DashboardEvent[] }
export interface DashboardConversation { session_id:string; status:string; started_at:string; ended_at?:string|null; duration_seconds:number; name?:string|null; phone?:string|null; conversation_type:string; intent?:string|null; confidence?:number|null; lead_score:number; escalation_status?:string|null; appointment_status?:string|null; followup_status?:string|null; summary?:string|null; next_action?:string|null; workflow_id?:string|null; messages?:Array<{speaker:string;text:string;timestamp:string;intent?:string|null}>; knowledge_sources?:DashboardKnowledgeSource[] }
export interface DashboardKnowledgeSource { document_id:string; filename:string; relative_path:string; document_type:string; page_or_slide?:string|null; section?:string|null; chunk_preview:string; relevance_score:number; query:string; used_at?:string|null }
export interface DashboardWorkflow { workflow_id:string; workflow_type:string; status:string; current_step?:string|null; previous_step?:string|null; next_step?:string|null; started_at:string; updated_at:string; retry_count:number; waiting:boolean; approval_status?:string|null; error?:string|null; session_id?:string|null; lead_id?:string|null }
export interface DashboardLead { lead_id:string; name?:string|null; phone?:string|null; email?:string|null; lead_type?:string|null; category?:string|null; budget?:string|number|null; property?:string|null; desired_time?:string|null; lead_score:number; status:string; open_items:string[]; next_action?:string|null; last_contact?:string|null; session_id?:string|null; workflow_id?:string|null }
export interface DashboardStatistics { conversations:number; active_conversations:number; completed_conversations:number; average_duration_seconds:number; new_leads:number; average_lead_score:number; seller_leads:number; investment_leads:number; appointments:number; followups:number; escalations:number; abandoned_conversations:number; knowledge_lookups:number; successful_workflows:number; failed_workflows:number }
