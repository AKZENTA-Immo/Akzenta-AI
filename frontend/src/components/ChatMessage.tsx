import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ChatResponse } from '../models/api'
import { SourceCard } from './SourceCard'

export function ChatMessage({ response }: { response: ChatResponse }) {
  const [copied, setCopied] = useState(false)
  const sources = response.quellen ?? []

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(response.antwort || '')
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className="chat-message">
      <div className="message-row message-ai">
        <div className="message-avatar ai-avatar">A</div>
        <div className="message-card">
          <div className="message-heading">
            <strong>AKZENTA AI</strong>
            <time>{response.dauer_sekunden != null ? `${response.dauer_sekunden.toFixed(1)} s` : 'gerade eben'}</time>
          </div>

          <div className="answer-markdown">
            <ReactMarkdown skipHtml>{response.antwort || 'Keine Antwort verfügbar.'}</ReactMarkdown>
          </div>

          <div className="answer-footer">
            <div className="answer-meta">
              {response.verwendetes_chat_modell && <span>Modell: {response.verwendetes_chat_modell}</span>}
            </div>
            <button type="button" className="chat-tool-button" onClick={() => void copyAnswer()}>
              {copied ? 'Kopiert' : 'Antwort kopieren'}
            </button>
          </div>

          {sources.length > 0 && (
            <section className="sources">
              <h3>Verwendete Quellen <span>{sources.length}</span></h3>
              <div className="source-grid">
                {sources.map((source) => (
                  <SourceCard key={`${source.dokument_id}-${source.quellen_nummer}`} source={source} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </article>
  )
}
