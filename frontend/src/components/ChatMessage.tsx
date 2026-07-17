import ReactMarkdown from 'react-markdown'
import type { ChatResponse } from '../models/api'
import { SourceCard } from './SourceCard'

export function ChatMessage({ response }: { response: ChatResponse }) {
  const sources = response.quellen ?? []
  return (
    <article className="chat-message">
      <div className="question-label">Ihre Frage</div>
      <p className="question-text">{response.frage}</p>
      <div className="answer-markdown"><ReactMarkdown skipHtml>{response.antwort || 'Keine Antwort verfügbar.'}</ReactMarkdown></div>
      <div className="answer-meta">
        {response.verwendetes_chat_modell && <span>Modell: {response.verwendetes_chat_modell}</span>}
        {response.dauer_sekunden != null && <span>Dauer: {response.dauer_sekunden.toFixed(1)} s</span>}
      </div>
      {sources.length > 0 && <section className="sources"><h3>Quellen ({sources.length})</h3>{sources.map((source) => <SourceCard key={`${source.dokument_id}-${source.quellen_nummer}`} source={source} />)}</section>}
    </article>
  )
}
