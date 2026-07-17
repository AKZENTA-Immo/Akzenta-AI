import { useState } from 'react'
import { AppLayout } from './components/AppLayout'
import type { Page } from './components/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { KnowledgePage } from './pages/KnowledgePage'

function Placeholder({ title }: { title: string }) {
  return (
    <div className="page placeholder">
      <span className="eyebrow">AKZENTA IMMOBILIEN</span>
      <h1>{title}</h1>
      <p>Dieser Bereich folgt in einer späteren Version.</p>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const labels: Record<Page, string> = {
    dashboard: 'Dashboard',
    chat: 'AKZENTA AI',
    knowledge: 'Wissensbasis',
    documents: 'Dokumente',
    sellers: 'Verkäufer',
    objects: 'Objekte',
    leads: 'Leads',
    marketing: 'Marketing',
    phone: 'Telefon-Agent',
    settings: 'Einstellungen',
  }

  let content

  switch (page) {
    case 'dashboard':
      content = <DashboardPage />
      break
    case 'chat':
      content = <ChatPage />
      break
    case 'knowledge':
      content = <KnowledgePage />
      break
    case 'documents':
      content = <DocumentsPage onUseInChat={() => setPage('chat')} />
      break
    default:
      content = <Placeholder title={labels[page]} />
  }

  return (
    <AppLayout page={page} onChange={setPage}>
      {content}
    </AppLayout>
  )
}
