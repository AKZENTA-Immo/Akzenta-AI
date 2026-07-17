interface StatusCardProps {
  label: string
  value: string | number
  state?: 'ready' | 'warning' | 'error' | 'neutral'
}

export function StatusCard({ label, value, state = 'neutral' }: StatusCardProps) {
  const displayValue = typeof value === 'number' ? value.toLocaleString('de-DE') : value
  return <div className={`status-card status-${state}`}><span className="status-dot" /><div><small>{label}</small><strong>{displayValue}</strong></div></div>
}
