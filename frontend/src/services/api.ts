import type { BackendInfo, ChatRequest, ChatResponse, ChatStatus, DocumentDetails, DocumentFilters, DocumentListResponse, DocumentSectionsResponse, DocumentStatistics, IndexingResponse, KnowledgeStatus } from '../models/api'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8010').replace(/\/$/, '')
const REQUEST_TIMEOUT_MS = 210_000

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort('timeout'), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: options.signal ?? controller.signal,
      headers: { Accept: 'application/json', ...options.headers },
    })
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new ApiError('Der Server hat eine ungültige Antwort geliefert.', response.status)
    }
    if (!response.ok) {
      const detail = typeof body === 'object' && body !== null && 'detail' in body ? String(body.detail) : ''
      throw new ApiError(detail || 'Die Anfrage konnte nicht verarbeitet werden.', response.status)
    }
    return body as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Die Anfrage wurde abgebrochen oder hat zu lange gedauert.')
    }
    throw new ApiError('Das AKZENTA-Backend ist nicht erreichbar.')
  } finally {
    window.clearTimeout(timeout)
  }
}

export const getBackendInfo = (): Promise<BackendInfo> => requestJson('/')
export const getChatStatus = (): Promise<ChatStatus> => requestJson('/chat/status')
export const getKnowledgeStatus = (): Promise<KnowledgeStatus> => requestJson('/wissensbasis/status')

export const sendDocumentQuestion = (request: ChatRequest): Promise<ChatResponse> =>
  requestJson('/chat/dokumente', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ frage: request.frage, limit: request.limit ?? 5 }),
  })

export const startIndexing = (): Promise<IndexingResponse> =>
  requestJson('/wissensbasis/indexieren', { method: 'POST' })

export const getDocuments = (filters: DocumentFilters, signal?: AbortSignal): Promise<DocumentListResponse> => {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => { if (value !== '') params.set(key, String(value)) })
  return requestJson(`/dokumente?${params}`, { signal })
}

export const getDocumentDetails = (id: string, signal?: AbortSignal): Promise<DocumentDetails> => requestJson(`/dokumente/${encodeURIComponent(id)}`, { signal })
export const getDocumentSections = (id: string, limit = 5, offset = 0, signal?: AbortSignal): Promise<DocumentSectionsResponse> => requestJson(`/dokumente/${encodeURIComponent(id)}/abschnitte?limit=${limit}&offset=${offset}`, { signal })
export const getDocumentStatistics = (signal?: AbortSignal): Promise<DocumentStatistics> => requestJson('/dokumente/statistik', { signal })
