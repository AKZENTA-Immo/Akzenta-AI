import { useEffect, useState, type ReactNode } from 'react'
import type { ChatStatus, KnowledgeStatus } from '../models/api'
import { getChatStatus, getKnowledgeStatus } from '../services/api'
import { AppHeader } from './AppHeader'
import { Sidebar, type Page } from './Sidebar'

export function AppLayout({ page, onChange, children }: { page: Page; onChange: (page: Page) => void; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [chat, setChat] = useState<ChatStatus | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeStatus | null>(null)
  useEffect(() => { void Promise.all([getChatStatus(), getKnowledgeStatus()]).then(([c, k]) => { setChat(c); setKnowledge(k) }).catch(() => undefined) }, [])
  return <div className={`app-shell ${collapsed ? 'shell-collapsed' : ''}`}><Sidebar page={page} collapsed={collapsed} onChange={onChange} onToggle={() => setCollapsed((value) => !value)} /><div className="workspace"><AppHeader chat={chat} knowledge={knowledge} /><main className="main-content">{children}</main></div></div>
}
