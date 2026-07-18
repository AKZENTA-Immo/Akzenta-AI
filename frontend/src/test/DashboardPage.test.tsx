import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '../pages/DashboardPage'
import * as api from '../services/api'

describe('DashboardPage onOffice status', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getBackendInfo').mockResolvedValue({ status: 'ok', branche: 'Immobilienmakler', version: '1.5' })
    vi.spyOn(api, 'getChatStatus').mockResolvedValue({ ollama_erreichbar: true, chat_modell_verfuegbar: true, chat_modell: 'llama3', embedding_modell: 'nomic', chromadb_erreichbar: true, indexierte_dokumente: 1, gespeicherte_abschnitte: 2, chat_bereit: true })
    vi.spyOn(api, 'getKnowledgeStatus').mockResolvedValue({ chromadb_erreichbar: true, collection_name: 'test', indexierte_dokumente: 1, gespeicherte_abschnitte: 2, embedding_modell: 'nomic', speicherort: 'data', letzte_indexierung: null })
    vi.spyOn(api, 'getDocumentStatistics').mockResolvedValue({ gesamt: 1, nach_dateityp: {}, nach_hauptordner: {}, lesbar: 1, fehlerhaft: 0, indexiert: 1, nicht_indexiert: 0, gesamtgroesse_bytes: 1, abschnitte_gesamt: 1 })
  })

  it('zeigt den deaktivierten sicheren Standardmodus', async () => {
    vi.spyOn(api, 'getOnOfficeStatus').mockResolvedValue({ enabled: false, mode: 'mock', configured: false, reachable: false, authenticated: false, api_url: 'https://api.onoffice.de/api/stable/api.php', permissions_checked: false })
    render(<DashboardPage />)
    expect(await screen.findByText('Deaktiviert')).toBeInTheDocument()
    expect(screen.getByText('Nicht konfiguriert')).toBeInTheDocument()
  })

  it('zeigt einen verbundenen Lesemodus', async () => {
    vi.spyOn(api, 'getOnOfficeStatus').mockResolvedValue({ enabled: true, mode: 'readonly', configured: true, reachable: true, authenticated: true, api_url: 'https://api.onoffice.de/api/stable/api.php', permissions_checked: true })
    render(<DashboardPage />)
    expect(await screen.findByText('Lesemodus verbunden')).toBeInTheDocument()
  })
})
