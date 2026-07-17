import { useEffect, useRef, useState } from 'react'

interface ChatInputProps {
  onSubmit: (question: string) => void
  loading: boolean
  initialValue?: string
}

export function ChatInput({ onSubmit, loading, initialValue = '' }: ChatInputProps) {
  const [question, setQuestion] = useState(initialValue)
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { ref.current?.focus() }, [])
  useEffect(() => { setQuestion(initialValue); ref.current?.focus() }, [initialValue])

  const submit = () => {
    const trimmed = question.trim()
    if (trimmed.length < 3 || loading) return
    onSubmit(trimmed)
    setQuestion('')
  }

  return (
    <div className="chat-input-wrap">
      <textarea
        ref={ref}
        value={question}
        maxLength={2000}
        rows={4}
        aria-label="Frage an AKZENTA AI"
        placeholder="Stellen Sie eine Frage zu Ihren internen Dokumenten …"
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit() }
        }}
      />
      <div className="input-footer">
        <span>{question.length} / 2000</span>
        <button className="primary-button" onClick={submit} disabled={loading || question.trim().length < 3}>
          {loading ? 'Antwort wird erstellt …' : 'Frage senden'}
        </button>
      </div>
    </div>
  )
}
