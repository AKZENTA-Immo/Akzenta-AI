import { useEffect, useState } from 'react'
import type { ChatStatus, IndexingResponse, KnowledgeStatus } from '../models/api'
import { getChatStatus, getKnowledgeStatus, startIndexing } from '../services/api'
import { ErrorMessage } from '../components/ErrorMessage'
import { IndexingResult } from '../components/IndexingResult'
import { LoadingIndicator } from '../components/LoadingIndicator'
import { StatusCard } from '../components/StatusCard'

export function KnowledgePage() {
  const [knowledge, setKnowledge] = useState<KnowledgeStatus | null>(null)
  const [chat, setChat] = useState<ChatStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [indexing, setIndexing] = useState(false)
  const [result, setResult] = useState<IndexingResponse | null>(null)
  const [error, setError] = useState('')

  const loadStatus = async () => {
    setLoading(true); setError('')
    try { const [k, c] = await Promise.all([getKnowledgeStatus(), getChatStatus()]); setKnowledge(k); setChat(c) }
    catch (err) { setError(err instanceof Error ? err.message : 'Status konnte nicht geladen werden.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void loadStatus() }, [])

  const index = async () => {
    setIndexing(true); setError(''); setResult(null)
    try { setResult(await startIndexing()); await loadStatus() }
    catch (err) { setError(err instanceof Error ? err.message : 'Indexierung fehlgeschlagen.') }
    finally { setIndexing(false) }
  }

  return (
    <div className="page knowledge-page">
      <header className="page-header"><div><span className="eyebrow">Lokale Dokumentensuche</span><h1>Wissensbasis</h1><p>Status und Aktualisierung des lokalen AKZENTA-Dokumentenindex.</p></div><button className="primary-button knowledge-action" onClick={index} disabled={indexing}>{indexing ? 'Indexierung läuft …' : 'Wissensbasis aktualisieren'}</button></header>
      {indexing && <div className="indexing-notice"><LoadingIndicator label="Dokumente werden geprüft und indexiert …" /><p>Dies kann abhängig vom Dokumentbestand einige Minuten dauern.</p></div>}
      {error && <ErrorMessage message={error} />}
      {loading && !knowledge ? <LoadingIndicator label="Status wird geladen …" /> : <>
        <section className="status-grid">
          <StatusCard label="ChromaDB" value={knowledge?.chromadb_erreichbar ? 'Erreichbar' : 'Nicht erreichbar'} state={knowledge?.chromadb_erreichbar ? 'ready' : 'error'} />
          <StatusCard label="Dokumentenchat" value={chat?.chat_bereit ? 'Bereit' : 'Nicht bereit'} state={chat?.chat_bereit ? 'ready' : 'warning'} />
          <StatusCard label="Ollama" value={chat?.ollama_erreichbar ? 'Erreichbar' : 'Nicht erreichbar'} state={chat?.ollama_erreichbar ? 'ready' : 'error'} />
          <StatusCard label="Chat-Modell" value={chat?.chat_modell_verfuegbar ? 'Verfügbar' : 'Fehlt'} state={chat?.chat_modell_verfuegbar ? 'ready' : 'warning'} />
          <StatusCard label="Dokumente" value={knowledge?.indexierte_dokumente ?? 0} />
          <StatusCard label="Textabschnitte" value={knowledge?.gespeicherte_abschnitte ?? 0} />
        </section>
        <section className="system-details"><h2>Systemdetails</h2><dl><div><dt>Collection</dt><dd>{knowledge?.collection_name ?? '–'}</dd></div><div><dt>Embedding-Modell</dt><dd>{knowledge?.embedding_modell ?? chat?.embedding_modell ?? '–'}</dd></div><div><dt>Chat-Modell</dt><dd>{chat?.chat_modell ?? '–'}</dd></div><div><dt>Letzte Indexierung</dt><dd>{knowledge?.letzte_indexierung ? new Date(knowledge.letzte_indexierung).toLocaleString('de-DE') : 'Noch nicht indexiert'}</dd></div><div><dt>Speicherort</dt><dd>{knowledge?.speicherort ?? '–'}</dd></div></dl></section>
      </>}
      {result && <IndexingResult result={result} />}
    </div>
  )
}
