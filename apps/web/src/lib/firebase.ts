import { initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth } from 'firebase/auth'

// Configuração exclusiva do projeto de demonstração local.
const firebaseConfig = {
  apiKey: 'demo-habilita-local',
  authDomain: 'demo-habilita.firebaseapp.com',
  projectId: 'demo-habilita',
}

// Evita utilizar esta configuração de demonstração em produção.
if (!import.meta.env.DEV) {
  throw new Error(
    'Firebase de produção ainda não configurado. ' +
      'Esta autenticação é exclusiva do ambiente local.',
  )
}

const app = initializeApp(firebaseConfig)

export const auth = getAuth(app)

// Conecta ao Firebase Auth Emulator.
connectAuthEmulator(auth, 'http://127.0.0.1:9099', {
  disableWarnings: true,
})
