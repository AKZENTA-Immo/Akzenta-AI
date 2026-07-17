import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { KnowledgePage } from '../pages/KnowledgePage'
import * as api from '../services/api'

vi.mock('../services/api', () => ({ getChatStatus: vi.fn(), getKnowledgeStatus: vi.fn(), startIndexing: vi.fn() }))
const getChat = vi.mocked(api.getChatStatus)
const getKnowledge = vi.mocked(api.getKnowledgeStatus)
const index = vi.mocked(api.startIndexing)

const knowledge = { chromadb_erreichbar: true, collection_name: 'akzenta_wissensbasis', indexierte_dokumente: 51, gespeicherte_abschnitte: 1134, embedding_modell: 'nomic-embed-text', speicherort: 'data/chroma', letzte_indexierung: '2026-07-17T10:00:00Z' }
const chat = { ollama_erreichbar: true, chat_modell_verfuegbar: true, chat_modell: 'llama3', embedding_modell: 'nomic-embed-text', chromadb_erreichbar: true, indexierte_dokumente: 51, gespeicherte_abschnitte: 1134, chat_bereit: true }

describe('KnowledgePage', () => {
  beforeEach(() => { vi.clearAllMocks(); getKnowledge.mockResolvedValue(knowledge); getChat.mockResolvedValue(chat) })

  it('zeigt den Wissensbasis-Status', async () => {
    render(<KnowledgePage />)
    expect(await screen.findByText('1.134')).toBeInTheDocument()
    expect(screen.getByText('nomic-embed-text')).toBeInTheDocument()
    expect(screen.getAllByText('Erreichbar')).toHaveLength(2)
  })

  it('startet Indexierung und zeigt das Ergebnis', async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.startIndexing>>) => void
    index.mockReturnValue(new Promise((done) => { resolve = done }))
    const user = userEvent.setup()
    render(<KnowledgePage />)
    await screen.findByText('1.134')
    await user.click(screen.getByRole('button', { name: 'Wissensbasis aktualisieren' }))
    expect(screen.getByText(/einige Minuten dauern/)).toBeInTheDocument()
    resolve({ status: 'ok', dokumente_gesamt: 52, neu_indexiert: 1, aktualisiert: 2, unveraendert: 48, entfernt: 0, fehlerhaft: 1, abschnitte_gesamt: 1140, dauer_sekunden: 8.2, fehler: [{ pfad: 'Datei.ppsx', ursache: 'Nicht lesbar' }] })
    await waitFor(() => expect(screen.getByRole('heading', { name: /Indexierung abgeschlossen/ })).toBeInTheDocument())
    expect(screen.getByText('1.140')).toBeInTheDocument()
    expect(screen.getByText(/Fehlerhafte Dokumente/)).toBeInTheDocument()
  })
})
