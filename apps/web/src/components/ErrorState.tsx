import './ErrorState.css'

type ErrorStateProps = {
  title?: string
  message: string
  onRetry: () => void
}

export function ErrorState({
  title = 'Não foi possível carregar os dados',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <span className="error-state__icon" aria-hidden="true">
        !
      </span>

      <div className="error-state__content">
        <h3>{title}</h3>

        <p>{message}</p>

        <button type="button" className="error-state__button" onClick={onRetry}>
          Tentar novamente
        </button>
      </div>
    </div>
  )
}
