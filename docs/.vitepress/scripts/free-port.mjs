import { createServer } from 'node:net'

function canBind(port) {
  return new Promise((resolve) => {
    const server = createServer()
    server.unref()
    server.on('error', () => resolve(false))
    server.listen(port, '127.0.0.1', () => {
      server.close(() => resolve(true))
    })
  })
}

const MIN_PORT = 5000
const MAX_PORT = 60000
const MAX_TRIES = 50

let port = null
for (let i = 0; i < MAX_TRIES; i++) {
  const candidate = MIN_PORT + Math.floor(Math.random() * (MAX_PORT - MIN_PORT))
  if (await canBind(candidate)) {
    port = candidate
    break
  }
}

if (port === null) {
  console.error('未能在 5000-60000 范围内找到可用端口')
  process.exit(1)
}

process.stdout.write(String(port))
