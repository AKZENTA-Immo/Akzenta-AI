import { useEffect, useRef, useState } from 'react'
import type { ChatResponse } from '../models/api'
import { sendDocumentQuestion } from '../services/api'
import { ChatInput } from '../components/ChatInput'
import { ChatMessage } from '../components/ChatMessage'
import { ErrorMessage } from '../components/ErrorMessage'
import { LoadingIndicator } from '../components/LoadingIndicator'

const suggestions = [
  'Welche Vorteile bietet eine Immobilie als Kapitalanlage?',
  'Welche steuerlichen Vorteile werden in unseren Unterlagen genannt?',
  'Was steht in unseren Dokumenten über Altersvorsorge?',
  'Wie läuft unser Verkäuferprozess ab?',
]

export function ChatPage() {
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [suggestion, setSuggestion] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [response, loading])

  const submit = async (frage: string) => {
    setLoading(true); setError(''); setSuggestion('')
    try { setResponse(await sendDocumentQuestion({ frage, limit: 5 })) }
    catch (err) { setError(err instanceof Error ? err.message : 'Die Anfrage konnte nicht verarbeitet werden.') }
    finally { setLoading(false) }
  }

  return (
    <div className="page chat-page">
      <header className="hero"><span className="eyebrow">Interner Immobilien-Assistent</span><h1>AKZENTA AI Chat</h1><p>Stellen Sie Fragen zu Ihrer internen Wissensbasis und erhalten Sie nachvollziehbare Antworten mit Quellen.</p></header>
      {!response && <section className="suggestions" aria-label="Beispielfragen"><span>Beispielfragen</span><div>{suggestions.map((item) => <button key={item} onClick={() => setSuggestion(item)}>{item}<b>→</b></button>)}</div></section>}
      {response && <ChatMessage response={response} />}
      {error && <ErrorMessage message={error} />}
      {loading && <LoadingIndicator label="AKZENTA AI durchsucht die Wissensbasis …" />}
      <ChatInput onSubmit={submit} loading={loading} initialValue={suggestion} />
      <p className="basis-hint">Antworten basieren ausschließlich auf der internen AKZENTA-Wissensbasis.</p>
      <div ref={endRef} />
    </div>
  )
}
