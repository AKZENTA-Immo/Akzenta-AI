import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatPage } from '../pages/ChatPage'
import * as api from '../services/api'

vi.mock('../services/api', () => ({ sendDocumentQuestion: vi.fn(), routeAgentMessage: vi.fn() }))
const send = vi.mocked(api.sendDocumentQuestion)
const route = vi.mocked(api.routeAgentMessage)

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.mockResolvedValue({ agent: 'dokumente', confidence: .9, reason: 'Dokumenten-Schlüsselwörter erkannt', original_message: 'Frage', simulation: true, result: { status: 'simulated', external_action_executed: false } })
  })

  it('wird mit Beispielfragen geladen', () => {
    render(<ChatPage />)
    expect(screen.getByRole('heading', { name: 'AKZENTA AI Chat' })).toBeInTheDocument()
    expect(screen.getByText(/Welche Vorteile bietet/)).toBeInTheDocument()
  })

  it('sendet eine Frage, zeigt Ladezustand, Antwort und Quellen', async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.sendDocumentQuestion>>) => void
    send.mockReturnValue(new Promise((done) => { resolve = done }))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.type(screen.getByLabelText('Frage an AKZENTA AI'), 'Welche Vorteile gibt es?')
    await user.click(screen.getByRole('button', { name: 'Frage senden' }))
    expect(screen.getByText(/durchsucht die Wissensbasis/)).toBeInTheDocument()
    resolve({
      frage: 'Welche Vorteile gibt es?', antwort: '**Inflationsschutz** und Rendite [Quelle 1].',
      verwendetes_chat_modell: 'llama3', dauer_sekunden: 2.4,
      quellen: [{ quellen_nummer: 1, dokument_id: '1', dateiname: 'Leitfaden.pdf', relativer_pfad: 'Kapitalanlage/Leitfaden.pdf', abschnitt: 3, seite: 4, relevanz: .87, textausschnitt: 'Immobilien bieten Inflationsschutz.' }],
    })
    await waitFor(() => expect(screen.getByText('Inflationsschutz', { selector: 'strong' })).toBeInTheDocument())
    expect(screen.getByText('Leitfaden.pdf')).toBeInTheDocument()
    expect(screen.getByLabelText('Agenten-Zuordnung')).toHaveTextContent('Agent: dokumente')
    expect(screen.getByLabelText('Agenten-Zuordnung')).toHaveTextContent('Simulation aktiv')
    expect(send).toHaveBeenCalledWith({ frage: 'Welche Vorteile gibt es?', limit: 5 })
    expect(route).toHaveBeenCalledWith('Welche Vorteile gibt es?', true)
  })

  it('zeigt Backend-Fehler verständlich an', async () => {
    send.mockRejectedValue(new Error('Ollama ist nicht erreichbar.'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.type(screen.getByLabelText('Frage an AKZENTA AI'), 'Eine Frage')
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama ist nicht erreichbar.')
  })
})
