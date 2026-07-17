interface LoadingIndicatorProps {
  label?: string
}

export function LoadingIndicator({ label = 'Wird geladen …' }: LoadingIndicatorProps) {
  return <div className="loading" role="status"><span className="spinner" />{label}</div>
}
