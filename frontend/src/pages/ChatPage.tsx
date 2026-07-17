import { useEffect, useRef, useState } from 'react'
import type { ChatResponse } from '../models/api'
import { sendDocumentQuestion } from '../services/api'
import { ChatInput } from '../components/ChatInput'
import { ChatMessage } from '../components/ChatMessage'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingIndicator } from '../components/LoadingIndicator'

interface ChatHistoryItem {
  id: string
  frage: string
  response: ChatResponse
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

export function ChatPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [suggestion, setSuggestion] = useState(() => {
    const value = sessionStorage.getItem('akzenta-document-question') || ''
    sessionStorage.removeItem('akzenta-document-question')
    return value
  })
  const [history, setHistory] = useState<ChatHistoryItem[]>(loadChatHistory)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth',
    })
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
      const answer = await sendDocumentQuestion({ frage, limit: 5 })
      setHistory((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          frage,
          response: answer,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Die Anfrage konnte nicht verarbeitet werden.')
    } finally {
      setLoading(false)
    }
  }

  const clearHistory = () => {
    setHistory([])
    setError('')
    localStorage.removeItem(CHAT_STORAGE_KEY)
  }

  return (
    <div className="page chat-page">
      <header className="hero">
        <span className="eyebrow">Interner Immobilien-Assistent</span>
        <h1>AKZENTA AI Chat</h1>
        <p>Stellen Sie Fragen zu Ihrer internen Wissensbasis und erhalten Sie nachvollziehbare Antworten mit Quellen.</p>
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
          <div className="user-question">
            <strong>Sie</strong>
            <p>{item.frage}</p>
          </div>
          <ChatMessage response={item.response} />
        </div>
      ))}

      {error && <ErrorMessage message={error} />}
      {loading && <LoadingIndicator label="AKZENTA AI durchsucht die Wissensbasis …" />}

      <ChatInput onSubmit={submit} loading={loading} initialValue={suggestion} />
      <p className="basis-hint">Antworten basieren ausschließlich auf der internen AKZENTA-Wissensbasis.</p>

      {history.length > 0 && (
        <button type="button" onClick={clearHistory}>
          Chat leeren
        </button>
      )}

      <div ref={endRef} />
    </div>
  )
}
