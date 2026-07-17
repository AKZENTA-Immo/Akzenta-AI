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
