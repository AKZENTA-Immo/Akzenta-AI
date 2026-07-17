import { BarChart3, Bot, Building2, ChevronLeft, ChevronRight, FileText, Home, Lightbulb, Megaphone, Phone, Settings, Users } from 'lucide-react'
import logo from '../assets/akzenta-logo-original.png'

export type Page = 'dashboard' | 'chat' | 'knowledge' | 'documents' | 'sellers' | 'objects' | 'leads' | 'marketing' | 'phone' | 'settings'

const items = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 }, { id: 'chat', label: 'AKZENTA AI', icon: Bot },
  { id: 'knowledge', label: 'Wissensbasis', icon: Lightbulb }, { id: 'documents', label: 'Dokumente', icon: FileText },
  { id: 'sellers', label: 'Verkäufer', icon: Users }, { id: 'objects', label: 'Objekte', icon: Building2 },
  { id: 'leads', label: 'Leads', icon: Home }, { id: 'marketing', label: 'Marketing', icon: Megaphone },
  { id: 'phone', label: 'Telefon-Agent', icon: Phone }, { id: 'settings', label: 'Einstellungen', icon: Settings },
] satisfies Array<{ id: Page; label: string; icon: typeof BarChart3 }>

interface SidebarProps { page: Page; collapsed: boolean; onChange: (page: Page) => void; onToggle: () => void }

export function Sidebar({ page, collapsed, onChange, onToggle }: SidebarProps) {
  return <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <div className="sidebar-brand"><div><strong>AKZENTA AI</strong><small>Interner Immobilien-Assistent</small></div></div>
    <button className="sidebar-toggle" onClick={onToggle} aria-label={collapsed ? 'Navigation ausklappen' : 'Navigation einklappen'}>{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</button>
    <nav aria-label="Hauptnavigation">{items.map(({ id, label, icon: Icon }) => <button key={id} title={collapsed ? label : undefined} className={page === id ? 'active' : ''} onClick={() => onChange(id)}><Icon aria-hidden="true" size={19} strokeWidth={1.8} /><span>{label}</span></button>)}</nav>
    <div className="sidebar-footer"><img src={logo} alt="AKZENTA Immobilien" /><span>Version 0.8</span></div>
  </aside>
}
