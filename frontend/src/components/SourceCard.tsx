import { FileText } from 'lucide-react'
import type { ChatSource } from '../models/api'

export function SourceCard({ source }: { source: ChatSource }) {
  const relevance = Math.max(0, Math.min(100, Math.round((source.relevanz ?? 0) * 100)))
  return (
    <details className="source-card">
      <summary>
        <span className="source-number"><FileText size={16} /><b>{source.quellen_nummer}</b></span>
        <span><strong>{source.dateiname || 'Unbenannte Quelle'}</strong><small>{source.relativer_pfad || 'Kein Pfad angegeben'}</small></span>
        <span className="relevance">{relevance} %</span>
      </summary>
      <div className="source-details">
        <dl>
          <div><dt>Abschnitt</dt><dd>{source.abschnitt ?? '–'}</dd></div>
          {source.seite != null && <div><dt>Seite</dt><dd>{source.seite}</dd></div>}
          {source.folie != null && <div><dt>Folie</dt><dd>{source.folie}</dd></div>}
          {source.tabellenblatt && <div><dt>Tabellenblatt</dt><dd>{source.tabellenblatt}</dd></div>}
        </dl>
        <p>{source.textausschnitt || 'Kein Textausschnitt verfügbar.'}</p>
      </div>
    </details>
  )
}
