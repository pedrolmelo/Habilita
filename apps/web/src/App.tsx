import { useEffect, useState } from 'react'
import { FormField } from './components/FormField'

// Os três estados que o bloco de saúde pode ter.
// Estado "vazio" não se aplica aqui: a resposta de /healthz nunca é uma lista.
// Nas telas com listas (próximas histórias), lembre de tratar o estado vazio também.
type HealthState =
  { kind: 'loading' } | { kind: 'success'; status: string } | { kind: 'error'; message: string }

// TODO: trocar por tipos gerados do OpenAPI quando a geração existir.
function isHealthResponse(data: unknown): data is { status: string } {
  return (
    typeof data === 'object' && data !== null && 'status' in data && typeof data.status === 'string'
  )
}

function HealthBlock() {
  const [state, setState] = useState<HealthState>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()

    async function check(): Promise<void> {
      try {
        // /api/healthz passa pelo proxy do Vite e chega em GET /healthz da API.
        const response = await fetch('/api/healthz', { signal: controller.signal })
        if (!response.ok) {
          setState({ kind: 'error', message: `A API respondeu com HTTP ${response.status}` })
          return
        }
        const data: unknown = await response.json()
        if (!isHealthResponse(data)) {
          setState({ kind: 'error', message: 'Resposta da API em formato inesperado' })
          return
        }
        setState({ kind: 'success', status: data.status })
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setState({ kind: 'error', message: 'Não foi possível falar com a API' })
      }
    }

    void check()
    return () => {
      controller.abort()
    }
  }, [])

  return (
    <section aria-live="polite">
      <h2>Estado da API</h2>
      {state.kind === 'loading' && <p>Carregando…</p>}
      {state.kind === 'success' && <p>API no ar: {state.status}</p>}
      {state.kind === 'error' && <p role="alert">Erro: {state.message}</p>}
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
