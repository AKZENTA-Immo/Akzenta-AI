export type Page = 'chat' | 'knowledge' | 'documents' | 'settings'

const items: Array<{ id: Page; label: string; icon: string }> = [
  { id: 'chat', label: 'Chat', icon: '✦' },
  { id: 'knowledge', label: 'Wissensbasis', icon: '▤' },
  { id: 'documents', label: 'Dokumente', icon: '□' },
  { id: 'settings', label: 'Einstellungen', icon: '⚙' },
]

export function Sidebar({ page, onChange }: { page: Page; onChange: (page: Page) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">A</span><div><strong>AKZENTA</strong><small>AI Workspace</small></div></div>
      <nav aria-label="Hauptnavigation">{items.map((item) => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => onChange(item.id)}><span>{item.icon}</span>{item.label}</button>)}</nav>
      <div className="privacy-note"><span className="status-dot" /><div><strong>Vollständig lokal</strong><small>Ihre Daten bleiben auf diesem Gerät.</small></div></div>
    </aside>
  )
}
