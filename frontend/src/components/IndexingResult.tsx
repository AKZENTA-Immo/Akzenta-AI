import type { IndexingResponse } from '../models/api'

export function IndexingResult({ result }: { result: IndexingResponse }) {
  const values = [
    ['Neu indexiert', result.neu_indexiert], ['Aktualisiert', result.aktualisiert],
    ['Unverändert', result.unveraendert], ['Entfernt', result.entfernt],
    ['Fehlerhaft', result.fehlerhaft], ['Abschnitte gesamt', result.abschnitte_gesamt],
  ] as const
  return (
    <section className="index-result" aria-label="Indexierungsergebnis">
      <h3>Indexierung abgeschlossen <small>{result.dauer_sekunden != null ? `${result.dauer_sekunden.toFixed(1)} s` : 'Dauer unbekannt'}</small></h3>
      <div className="result-grid">{values.map(([label, value]) => <div key={label}><span>{label}</span><strong>{(value ?? 0).toLocaleString('de-DE')}</strong></div>)}</div>
      {(result.fehler ?? []).length > 0 && <details className="index-errors"><summary>Fehlerhafte Dokumente ({result.fehler?.length})</summary><ul>{result.fehler?.map((error) => <li key={error.pfad}><strong>{error.pfad}</strong><span>{error.ursache}</span></li>)}</ul></details>}
    </section>
  )
}
