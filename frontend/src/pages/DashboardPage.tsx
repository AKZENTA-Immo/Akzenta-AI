import { useCallback, useEffect, useState } from 'react'
import type { BackendInfo, ChatStatus, DocumentStatistics, KnowledgeStatus } from '../models/api'
import { getBackendInfo, getChatStatus, getDocumentStatistics, getKnowledgeStatus } from '../services/api'

interface DashboardData {
  backend: BackendInfo
  chat: ChatStatus
  knowledge: KnowledgeStatus
  documents: DocumentStatistics
  responseTimeMs: number
}

function StatusCard({ label, value, ok }: { label: string; value: string | number; ok: boolean }) {
  return (
    <article className={`status-card ${ok ? '' : 'status-error'}`}>
      <span className="status-icon" aria-hidden="true"><span className="status-dot" /></span>
      <div>
        <strong>{value}</strong>
        <small>{label}</small>
      </div>
    </article>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadStatus = useCallback(async () => {
    setLoading(true)
    setError('')
    const startedAt = performance.now()

    try {
      const [backend, chat, knowledge, documents] = await Promise.all([
        getBackendInfo(),
        getChatStatus(),
        getKnowledgeStatus(),
        getDocumentStatistics(),
      ])

      setData({
        backend,
        chat,
        knowledge,
        documents,
        responseTimeMs: Math.round(performance.now() - startedAt),
      })
    } catch (err) {
      setData(null)
      setError(err instanceof Error ? err.message : 'Der Systemstatus konnte nicht geladen werden.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <span className="eyebrow">AKZENTA IMMOBILIEN</span>
          <h1>System-Dashboard</h1>
          <p>Live-Status von Backend, Ollama, Wissensbasis und Dokumentenbestand.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => void loadStatus()} disabled={loading}>
          {loading ? 'Prüfung läuft …' : 'Status aktualisieren'}
        </button>
      </header>

      {error && <div className="error-message">{error}</div>}

      {data && (
        <>
          <section className="status-grid" aria-label="Systemstatus">
            <StatusCard label="Backend" value="Online" ok />
            <StatusCard label="Ollama" value={data.chat.ollama_erreichbar ? 'Online' : 'Offline'} ok={data.chat.ollama_erreichbar} />
            <StatusCard label="Chat-Modell" value={data.chat.chat_modell} ok={data.chat.chat_modell_verfuegbar} />
            <StatusCard label="Wissensbasis" value={data.chat.chat_bereit ? 'Bereit' : 'Nicht bereit'} ok={data.chat.chat_bereit} />
            <StatusCard label="Dokumente" value={data.documents.gesamt} ok={data.documents.gesamt > 0} />
            <StatusCard label="Antwortzeit" value={`${data.responseTimeMs} ms`} ok={data.responseTimeMs < 5000} />
          </section>

          <section className="system-details">
            <h2>Systemdetails</h2>
            <dl>
              <div><dt>AKZENTA-AI-Version</dt><dd>{data.backend.version}</dd></div>
              <div><dt>Backend-Status</dt><dd>{data.backend.status}</dd></div>
              <div><dt>Chat-Modell</dt><dd>{data.chat.chat_modell}</dd></div>
              <div><dt>Embedding-Modell</dt><dd>{data.chat.embedding_modell}</dd></div>
              <div><dt>ChromaDB</dt><dd>{data.chat.chromadb_erreichbar ? 'Erreichbar' : 'Nicht erreichbar'}</dd></div>
              <div><dt>Indexierte Dokumente</dt><dd>{data.chat.indexierte_dokumente}</dd></div>
              <div><dt>Gespeicherte Abschnitte</dt><dd>{data.chat.gespeicherte_abschnitte}</dd></div>
              <div><dt>Letzte Indexierung</dt><dd>{data.knowledge.letzte_indexierung || 'Noch nicht verfügbar'}</dd></div>
            </dl>
          </section>

          {data.chat.fehlermeldung && <div className="error-message">{data.chat.fehlermeldung}</div>}
        </>
      )}
    </div>
  )
}
