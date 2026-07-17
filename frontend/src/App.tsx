import { useState } from 'react'
import { AppLayout } from './components/AppLayout'
import type { Page } from './components/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { KnowledgePage } from './pages/KnowledgePage'

function Placeholder({ title }: { title: string }) {
  return <div className="page placeholder"><span className="eyebrow">AKZENTA IMMOBILIEN</span><h1>{title}</h1><p>Dieser Bereich folgt in einer späteren Version.</p></div>
}

export default function App() {
  const [page, setPage] = useState<Page>('chat')
  const labels: Record<Page, string> = { dashboard: 'Dashboard', chat: 'AKZENTA AI', knowledge: 'Wissensbasis', documents: 'Dokumente', sellers: 'Verkäufer', objects: 'Objekte', leads: 'Leads', marketing: 'Marketing', phone: 'Telefon-Agent', settings: 'Einstellungen' }
  return <AppLayout page={page} onChange={setPage}>{page === 'chat' ? <ChatPage /> : page === 'knowledge' ? <KnowledgePage /> : <Placeholder title={labels[page]} />}</AppLayout>
}
