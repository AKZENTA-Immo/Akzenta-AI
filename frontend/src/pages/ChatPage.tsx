import { useEffect, useRef, useState } from 'react'
import type { AgentExecutionResponse, AgentManagerResponse, ChatResponse } from '../models/api'
import { executeAgentMessage, sendDocumentQuestion } from '../services/api'
import { ChatInput } from '../components/ChatInput'
import { ChatMessage } from '../components/ChatMessage'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingIndicator } from '../components/LoadingIndicator'

interface ChatHistoryItem {
  id: string
  frage: string
  response: ChatResponse
  routing?: AgentManagerResponse
  execution?: AgentExecutionResponse
}

const CHAT_STORAGE_KEY = 'akzenta-chat-history'

const suggestions = [
  'Welche Vorteile bietet eine Immobilie als Kapitalanlage?',
  'Welche steuerlichen Vorteile werden in unseren Unterlagen genannt?',
  'Was steht in unseren Dokumenten über Altersvorsorge?',
  'Wie läuft unser Verkäuferprozess ab?',
]

function loadChatHistory(): ChatHistoryItem[] {
  try {
    const savedHistory = localStorage.getItem(CHAT_STORAGE_KEY)

    if (!savedHistory) {
      return []
    }

    const parsedHistory: unknown = JSON.parse(savedHistory)
    return Array.isArray(parsedHistory) ? (parsedHistory as ChatHistoryItem[]) : []
  } catch {
    localStorage.removeItem(CHAT_STORAGE_KEY)
    return []
  }
}

function buildExport(history: ChatHistoryItem[]): string {
  const header = `# AKZENTA AI Chat\n\nExportiert am ${new Date().toLocaleString('de-DE')}\n`
  const conversations = history.map((item, index) => [
    `## Gespräch ${index + 1}`,
    '',
    `**Frage:** ${item.frage}`,
    '',
    '**Antwort:**',
    item.response.antwort || 'Keine Antwort verfügbar.',
    '',
    item.response.quellen?.length
      ? `**Quellen:** ${item.response.quellen.map((source) => source.dateiname).join(', ')}`
      : '**Quellen:** Keine',
  ].join('\n'))

  return `${header}\n${conversations.join('\n\n---\n\n')}\n`
}

export function ChatPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
  const [suggestion, setSuggestion] = useState(() => {
    const value = sessionStorage.getItem('akzenta-document-question') || ''
    sessionStorage.removeItem('akzenta-document-question')
    return value
  })
  const [history, setHistory] = useState<ChatHistoryItem[]>(loadChatHistory)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, loading])

  useEffect(() => {
    try {
      if (history.length === 0) {
        localStorage.removeItem(CHAT_STORAGE_KEY)
        return
      }

      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history))
    } catch {
      console.error('Chatverlauf konnte nicht gespeichert werden.')
    }
  }, [history])

  const submit = async (frage: string) => {
    setLoading(true)
    setError('')
    setSuggestion('')

    try {
      const [answer, execution] = await Promise.all([
        sendDocumentQuestion({ frage, limit: 5 }),
        executeAgentMessage(frage, true),
      ])
      setHistory((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          frage,
          response: answer,
          execution,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Die Anfrage konnte nicht verarbeitet werden.')
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async (item: ChatHistoryItem) => {
    setRegeneratingId(item.id)
    setError('')

    try {
      const answer = await sendDocumentQuestion({ frage: item.frage, limit: 5 })
      setHistory((previous) => previous.map((entry) => (
        entry.id === item.id ? { ...entry, response: answer } : entry
      )))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Die Antwort konnte nicht neu erstellt werden.')
    } finally {
      setRegeneratingId(null)
    }
  }

  const exportHistory = () => {
    const blob = new Blob([buildExport(history)], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `akzenta-chat-${new Date().toISOString().slice(0, 10)}.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  const clearHistory = () => {
    setHistory([])
    setError('')
    localStorage.removeItem(CHAT_STORAGE_KEY)
  }

  return (
    <div className="page chat-page">
      <header className="hero chat-hero">
        <div>
          <span className="eyebrow">Interner Immobilien-Assistent</span>
          <h1>AKZENTA AI Chat</h1>
          <p>Stellen Sie Fragen zu Ihrer internen Wissensbasis und erhalten Sie nachvollziehbare Antworten mit Quellen.</p>
        </div>

        {history.length > 0 && (
          <div className="chat-header-actions">
            <button type="button" className="chat-tool-button" onClick={exportHistory}>Chat exportieren</button>
            <button type="button" className="chat-tool-button danger" onClick={clearHistory}>Chat leeren</button>
          </div>
        )}
      </header>

      {history.length === 0 && (
        <section className="suggestions" aria-label="Beispielfragen">
          <span>Beispielfragen</span>
          <div>
            {suggestions.map((item) => (
              <button key={item} onClick={() => setSuggestion(item)}>
                {item}
                <b>→</b>
              </button>
            ))}
          </div>
        </section>
      )}

      {history.map((item) => (
        <div key={item.id} className="conversation">
          <div className="message-row message-user">
            <div className="message-avatar user-avatar">S</div>
            <div className="message-card">
              <div className="message-heading"><strong>Sie</strong><time>gespeichert</time></div>
              <p>{item.frage}</p>
            </div>
          </div>

          <ChatMessage response={item.response} />

          {item.routing && (
            <div className="agent-routing" aria-label="Agenten-Zuordnung">
              <b>Nur zugeordnet</b>
              <strong>Agent: {item.routing.agent.replace('_', ' ')}</strong>
              <span>{item.routing.reason}</span>
              <span>{item.routing.simulation ? 'Simulation aktiv' : 'Ausführung blockiert'}</span>
            </div>
          )}

          {item.execution && (
            <section className="agent-execution" aria-label="Agentenausführung">
              <header><b>Agent ausgeführt</b><strong>{item.execution.agent.replace('_', ' ')}</strong><span>{Math.round(item.execution.confidence * 100)} % Sicherheit{item.execution.uncertain ? ' · Zuordnung unsicher' : ''}</span></header>
              <p>{item.execution.reasoning}</p>
              <div className="agent-simulation-label">Simulation aktiv · {item.execution.approval_required ? 'Freigabe erforderlich' : 'Keine Freigabe erforderlich'}</div>
              <pre>{JSON.stringify(item.execution.result, null, 2)}</pre>
              {item.execution.missing_information.length > 0 && <div><b>Fehlende Angaben</b><ul>{item.execution.missing_information.map(value => <li key={value}>{value}</li>)}</ul></div>}
              {item.execution.proposed_actions.length > 0 && <div><b>Geplante Aktionen</b><ul>{item.execution.proposed_actions.map(value => <li key={value}>{value}</li>)}</ul></div>}
              {item.execution.warnings.map(value => <small key={value}>{value}</small>)}
            </section>
          )}

          <div className="conversation-actions">
            <button
              type="button"
              className="chat-tool-button"
              onClick={() => void regenerate(item)}
              disabled={regeneratingId !== null || loading}
            >
              {regeneratingId === item.id ? 'Antwort wird neu erstellt …' : 'Antwort neu erstellen'}
            </button>
          </div>
        </div>
      ))}

      {error && <ErrorMessage message={error} />}
      {loading && <LoadingIndicator label="AKZENTA AI durchsucht die Wissensbasis …" />}

      <ChatInput onSubmit={submit} loading={loading || regeneratingId !== null} initialValue={suggestion} />
      <p className="basis-hint">Antworten basieren ausschließlich auf der internen AKZENTA-Wissensbasis.</p>

      <div ref={endRef} />
    </div>
  )
}
