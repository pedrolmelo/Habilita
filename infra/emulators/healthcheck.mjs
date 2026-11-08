// Healthcheck dos emuladores: sai com 0 se as 4 portas aceitam conexão TCP, com 1 se não.
import net from 'node:net'

const PORTS = [9099, 8080, 9199, 4000] // Auth, Firestore, Storage, Interface

function canConnect(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port })
    socket.setTimeout(2000)
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('timeout', () => {
      socket.destroy()
      resolve(false)
    })
    socket.once('error', () => resolve(false))
  })
}

const results = await Promise.all(PORTS.map(canConnect))
process.exit(results.every(Boolean) ? 0 : 1)
