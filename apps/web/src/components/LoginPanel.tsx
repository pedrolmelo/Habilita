import { useEffect, useState, type FormEvent } from 'react'
import { FirebaseError } from 'firebase/app'
import {
  getIdTokenResult,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from 'firebase/auth'
import { auth } from '../lib/firebase'
import { FormField } from './FormField'

type Papel = 'gestor' | 'porteiro' | 'terceirizada'

type Sessao = {
  email: string
  papel: Papel
}

function isPapel(value: unknown): value is Papel {
  return value === 'gestor' || value === 'porteiro' || value === 'terceirizada'
}

async function carregarSessao(user: User): Promise<Sessao> {
  const token = await getIdTokenResult(user, true)
  const { papel, tenantId } = token.claims

  if (!isPapel(papel) || typeof tenantId !== 'string') {
    throw new Error('missing-claims')
  }

  return {
    email: user.email ?? 'Usuário',
    papel,
  }
}

function mensagemErro(error: unknown): string {
  if (error instanceof FirebaseError) {
    switch (error.code) {
      case 'auth/invalid-credential':
      case 'auth/wrong-password':
      case 'auth/user-not-found':
        return 'E-mail ou senha inválidos.'
      case 'auth/invalid-email':
        return 'Informe um e-mail válido.'
      case 'auth/user-disabled':
        return 'Esta conta está desativada.'
      case 'auth/network-request-failed':
        return 'Não foi possível conectar ao Firebase.'
      case 'auth/too-many-requests':
        return 'Muitas tentativas. Tente novamente mais tarde.'
    }
  }

  return 'Não foi possível concluir a autenticação.'
}

export function LoginPanel() {
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [sessao, setSessao] = useState<Sessao | null>(null)
  const [verificando, setVerificando] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true

    async function atualizarSessao(user: User | null): Promise<void> {
      if (!ativo) return

      setVerificando(true)

      if (!user) {
        setSessao(null)
        setVerificando(false)
        return
      }

      try {
        const dados = await carregarSessao(user)

        if (ativo) {
          setSessao(dados)
          setErro('')
        }
      } catch {
        if (ativo) {
          setSessao(null)
          setErro('Conta sem permissões válidas no Habilita.')
        }

        await signOut(auth).catch(() => undefined)
      } finally {
        if (ativo) {
          setVerificando(false)
        }
      }
    }

    const unsubscribe = onAuthStateChanged(
      auth,
      (user) => {
        void atualizarSessao(user)
      },
      () => {
        if (ativo) {
          setErro('Não foi possível recuperar a sessão.')
          setVerificando(false)
        }
      },
    )

    return () => {
      ativo = false
      unsubscribe()
    }
  }, [])

  async function entrar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setEnviando(true)

    try {
      await signInWithEmailAndPassword(auth, email.trim(), senha)
      setSenha('')
    } catch (error) {
      setErro(mensagemErro(error))
    } finally {
      setEnviando(false)
    }
  }

  async function sair() {
    setErro('')
    setEnviando(true)

    try {
      await signOut(auth)
      setSessao(null)
    } catch (error) {
      setErro(mensagemErro(error))
    } finally {
      setEnviando(false)
    }
  }

  if (verificando) {
    return (
      <section aria-live="polite">
        <h2>Acesso ao Habilita</h2>
        <p>Verificando autenticação...</p>
      </section>
    )
  }

  if (sessao) {
    return (
      <section aria-labelledby="session-title">
        <h2 id="session-title">Acesso autorizado</h2>
        <p role="status">Login realizado com sucesso!</p>
        <p>
          <strong>Usuário:</strong> {sessao.email}
        </p>
        <p>
          <strong>Perfil:</strong> {sessao.papel}
        </p>

        {erro && <p role="alert">{erro}</p>}

        <button type="button" onClick={() => void sair()} disabled={enviando}>
          {enviando ? 'Saindo...' : 'Sair'}
        </button>
      </section>
    )
  }

  return (
    <section aria-labelledby="login-title">
      <h2 id="login-title">Acesso ao Habilita</h2>
      <p>Informe suas credenciais para acessar a plataforma.</p>

      <form onSubmit={(event) => void entrar(event)}>
        <FormField
          id="login-email"
          label="E-mail"
          name="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          placeholder="Digite seu e-mail"
          required
          disabled={enviando}
        />

        <FormField
          id="login-password"
          label="Senha"
          name="password"
          type="password"
          value={senha}
          onChange={(event) => setSenha(event.target.value)}
          autoComplete="current-password"
          placeholder="Digite sua senha"
          required
          disabled={enviando}
        />

        {erro && <p role="alert">{erro}</p>}

        <button type="submit" disabled={enviando}>
          {enviando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </section>
  )
}
