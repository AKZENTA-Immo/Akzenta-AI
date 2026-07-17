import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AgentPage } from '../pages/AgentPage'

describe('AgentPage', () => {
  beforeEach(() => { vi.restoreAllMocks(); vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ agent: 'email', mode: 'draft', provider: 'Gmail', provider_connected: false, external_actions_enabled: false, prompt_version: 'v1', capabilities: ['draft'] }) })) })
  it('zeigt den sicheren Entwurfsmodus', async () => {
    render(<AgentPage agent="email" />)
    expect(screen.getByText('Externe Aktionen sind deaktiviert')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Gmail')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Entwurf erstellen' })).toBeInTheDocument()
  })
})
