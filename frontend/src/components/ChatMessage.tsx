import ReactMarkdown from 'react-markdown'
import type { ChatResponse } from '../models/api'
import { SourceCard } from './SourceCard'

export function ChatMessage({ response }: { response: ChatResponse }) {
  const sources = response.quellen ?? []
  return <article className="chat-message">
    <div className="message-row message-user"><div className="message-avatar user-avatar">S</div><div className="message-card"><div className="message-heading"><strong>Sie</strong><time>gerade eben</time></div><p>{response.frage}</p></div></div>
    <div className="message-row message-ai"><div className="message-avatar ai-avatar">A</div><div className="message-card"><div className="message-heading"><strong>AKZENTA AI</strong><time>{response.dauer_sekunden != null ? `${response.dauer_sekunden.toFixed(1)} s` : 'gerade eben'}</time></div><div className="answer-markdown"><ReactMarkdown skipHtml>{response.antwort || 'Keine Antwort verfügbar.'}</ReactMarkdown></div><div className="answer-meta">{response.verwendetes_chat_modell && <span>Modell: {response.verwendetes_chat_modell}</span>}</div>{sources.length > 0 && <section className="sources"><h3>Verwendete Quellen <span>{sources.length}</span></h3><div className="source-grid">{sources.map((source) => <SourceCard key={`${source.dokument_id}-${source.quellen_nummer}`} source={source} />)}</div></section>}</div></div>
  </article>
}
