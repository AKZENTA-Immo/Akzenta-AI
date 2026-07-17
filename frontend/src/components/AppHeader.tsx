import { Bot, Database, FileText, Layers3, UserRound } from 'lucide-react'
import type { ChatStatus, KnowledgeStatus } from '../models/api'

export function AppHeader({ chat, knowledge }: { chat: ChatStatus | null; knowledge: KnowledgeStatus | null }) {
  const cards = [
    { label: 'Ollama', value: chat?.ollama_erreichbar ? 'Bereit' : 'Offline', icon: Bot },
    { label: 'Wissensbasis', value: chat?.chat_bereit ? 'Bereit' : 'Prüfen', icon: Database },
    { label: 'Dokumente', value: knowledge?.indexierte_dokumente?.toLocaleString('de-DE') ?? '–', icon: FileText },
    { label: 'Abschnitte', value: knowledge?.gespeicherte_abschnitte?.toLocaleString('de-DE') ?? '–', icon: Layers3 },
    { label: 'Benutzer', value: 'Lokal', icon: UserRound },
  ]
  return <header className="app-header" aria-label="Systemstatus">{cards.map(({ label, value, icon: Icon }) => <div className="header-status" key={label}><Icon size={17} /><span><small>{label}</small><strong>{value}</strong></span></div>)}</header>
}
