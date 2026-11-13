import { useEffect, useState } from 'react'
import { ErrorState } from './components/ErrorState'
import { FormField } from './components/FormField'

type HealthState =
  { kind: 'loading' } | { kind: 'success'; status: string } | { kind: 'error'; message: string }

function isHealthResponse(data: unknown): data is { status: string } {
  return (
    typeof data === 'object' && data !== null && 'status' in data && typeof data.status === 'string'
  )
}

function HealthBlock() {
  const [state, setState] = useState<HealthState>({
    kind: 'loading',
  })

  const [tentativas, setTentativas] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function verificarAPI(): Promise<void> {
      try {
        // Se VITE_API_URL estiver definida (produção/Render), consome diretamente a API.
        // Se vazia ou não definida (ambiente local), mantém a chamada relativa '/api'
        // que passa pelo proxy do Vite e chega em GET /healthz da API.
        const apiBaseUrl = import.meta.env.VITE_API_URL
          ? import.meta.env.VITE_API_URL.replace(/\/+$/, '')
          : ''
        const url = apiBaseUrl ? `${apiBaseUrl}/healthz` : '/api/healthz'
        const response = await fetch(url, { signal: controller.signal })
        if (!response.ok) {
          setState({
            kind: 'error',
            message:
              `A API respondeu com HTTP ${response.status}. ` +
              'Verifique o serviço e tente novamente.',
          })
          return
        }

        const data: unknown = await response.json()

        if (controller.signal.aborted) return

        if (!isHealthResponse(data)) {
          setState({
            kind: 'error',
            message: 'A API retornou dados em formato inesperado.',
          })
          return
        }

        setState({
          kind: 'success',
          status: data.status,
        })
      } catch {
        if (controller.signal.aborted) return

        setState({
          kind: 'error',
          message: 'Não foi possível conectar à API. ' + 'Verifique sua conexão e tente novamente.',
        })
      }
    }

    void verificarAPI()

    return () => {
      controller.abort()
    }
  }, [tentativas])

  function tentarNovamente() {
    setState({ kind: 'loading' })
    setTentativas((atual) => atual + 1)
  }

  return (
    <section aria-live="polite">
      <h2>Estado da API</h2>

      {state.kind === 'loading' && <p>Carregando informações...</p>}

      {state.kind === 'success' && <p>API no ar: {state.status}</p>}

      {state.kind === 'error' && <ErrorState message={state.message} onRetry={tentarNovamente} />}
    </section>
  )
}

function LoginFormPreview() {
  return (
    <section aria-labelledby="login-title">
      <h2 id="login-title">Acesso ao Habilita</h2>

      <p>Informe suas credenciais para acessar a plataforma.</p>

      <form onSubmit={(event) => event.preventDefault()}>
        <FormField
          id="login-email"
          label="E-mail"
          name="email"
          type="email"
          placeholder="Digite seu e-mail"
          autoComplete="email"
          required
        />

        <FormField
          id="login-password"
          label="Senha"
          name="password"
          type="password"
          placeholder="Digite sua senha"
          autoComplete="current-password"
          required
        />

        <button type="submit" disabled>
          Entrar (em desenvolvimento)
        </button>
      </form>

      <p>Prévia dos campos acessíveis. A autenticação será integrada na FE-11.</p>
    </section>
  )
}

export default function App() {
  return (
    <main>
      <h1>Habilita</h1>

      <HealthBlock />

      <LoginFormPreview />
    </main>
  )
}
