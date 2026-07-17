import { useState } from 'react'
import { AppLayout } from './components/AppLayout'
import type { Page } from './components/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { DocumentsPage } from './pages/DocumentsPage'
import { AgentPage } from './pages/AgentPage'

function Placeholder({ title }: { title: string }) {
  return <div className="page placeholder"><span className="eyebrow">AKZENTA IMMOBILIEN</span><h1>{title}</h1><p>Dieser Bereich folgt in einer späteren Version.</p></div>
}

export default function App() {
  const [page, setPage] = useState<Page>('chat')
  const labels: Record<Page, string> = { dashboard: 'Dashboard', chat: 'AKZENTA AI', knowledge: 'Wissensbasis', documents: 'Dokumente', crm: 'CRM-Agent', email: 'E-Mail-Agent', calendar: 'Termin-Agent', sellers: 'Verkäufer', objects: 'Objekte', leads: 'Leads', marketing: 'Marketing', phone: 'Telefon-Agent', settings: 'Einstellungen' }
  return <AppLayout page={page} onChange={setPage}>{page === 'chat' ? <ChatPage /> : page === 'knowledge' ? <KnowledgePage /> : page === 'documents' ? <DocumentsPage onUseInChat={() => setPage('chat')} /> : page === 'crm' || page === 'email' || page === 'calendar' ? <AgentPage agent={page} /> : <Placeholder title={labels[page]} />}</AppLayout>
}
