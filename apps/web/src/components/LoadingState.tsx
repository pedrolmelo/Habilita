import './LoadingState.css'

type LoadingStateProps = {
  message?: string
}

export function LoadingState({ message = 'Verificando conexão com a API...' }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-atomic="true">
      <span className="loading-state__spinner" aria-hidden="true" />

      <span className="loading-state__message">{message}</span>
    </div>
  )
}
