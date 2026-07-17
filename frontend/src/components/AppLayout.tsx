import type { ReactNode } from 'react'
import { Sidebar, type Page } from './Sidebar'

export function AppLayout({ page, onChange, children }: { page: Page; onChange: (page: Page) => void; children: ReactNode }) {
  return <div className="app-shell"><Sidebar page={page} onChange={onChange} /><main className="main-content">{children}</main></div>
}
