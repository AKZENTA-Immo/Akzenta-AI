import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentsPage } from '../pages/DocumentsPage'

const doc = { dokument_id: 'a'.repeat(64), dateiname: 'AKZENTA.pdf', dateiendung: '.pdf', relativer_pfad: 'Ordner/AKZENTA.pdf', hauptordner: 'Ordner', dateigroesse_bytes: 2048, geaendert_am: '2026-07-17T10:00:00Z', lesbar: true, lesefehler: null, indexiert: true, abschnitt_anzahl: 1, seiten_oder_elemente: 1, mime_typ: 'application/pdf' }
const stats = { gesamt: 1, nach_dateityp: { '.pdf': 1 }, nach_hauptordner: { Ordner: 1 }, lesbar: 1, fehlerhaft: 0, indexiert: 1, nicht_indexiert: 0, gesamtgroesse_bytes: 2048, abschnitte_gesamt: 1 }

describe('DocumentsPage', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const body = url.endsWith('/statistik') ? stats : url.includes('/abschnitte') ? { gesamt: 1, limit: 5, offset: 0, abschnitte: [{ abschnitt_id: 'c', text: '<script>harmloser Text</script>', abschnittsnummer: 0, zeichenanzahl: 31, metadaten: {} }] } : /\/dokumente\/[a-f0-9]{64}$/.test(url) ? { ...doc, textauszug: 'Vorschautext', abschnittsmetadaten: {} } : { gesamt: 1, limit: 10, offset: 0, dokumente: [doc] }
    return { ok: true, status: 200, json: async () => body } as Response
  })))

  it('zeigt Statistik, Liste, Filter und Detailabschnitte', async () => {
    render(<DocumentsPage onUseInChat={vi.fn()} />)
    expect(screen.getByText('Dokumentencenter')).toBeInTheDocument()
    expect(await screen.findAllByText('AKZENTA.pdf')).not.toHaveLength(0)
    expect(screen.getByText('Dokumente gesamt')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Dateityp'), { target: { value: '.pdf' } })
    fireEvent.change(screen.getByLabelText('Dokumente durchsuchen'), { target: { value: 'AKZENTA' } })
    await waitFor(() => expect(fetch).toHaveBeenCalled())
    fireEvent.click(screen.getAllByText('Details')[0])
    expect(await screen.findByText('Vorschautext')).toBeInTheDocument()
    expect(await screen.findByText('<script>harmloser Text</script>')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
  })

  it('zeigt Lade-, Leer- und Fehlerzustände', async () => {
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => {}))
    render(<DocumentsPage onUseInChat={vi.fn()} />)
    expect(screen.getByText('Dokumente werden geladen …')).toBeInTheDocument()
  })
})
