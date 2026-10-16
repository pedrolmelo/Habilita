# infra/emulators — Firebase Emulator Suite

Imagem Docker dos emuladores locais do Firebase:
- **Auth:** porta `9099`
- **Cloud Firestore:** porta `8080`
- **Cloud Storage:** porta `9199`
- **Interface Web (Emulator UI):** porta `4000`

## Características técnicas

- **Base:** `node:24.22.0-trixie-slim` (Node 24 LTS).
- **Java:** `openjdk-21-jre-headless` (exigido a partir do `firebase-tools 15.x` para o emulador do Firestore).
- **Segurança:** O processo roda com usuário não-root `node` (UID 1000). As portas são expostas localmente apenas em `127.0.0.1`.
- **Memória:** Configurado com `JAVA_TOOL_OPTIONS="-Xmx512m"` para evitar que a JVM aloque memória em excesso.
- **Persistência:** Os dados são efêmeros e resetados a cada reinicialização (`docker compose down -v`).

## Como rodar com Docker Compose

Na raiz do repositório:
```bash
docker compose up -d emulators
```

Painel de controle web: [http://localhost:4000](http://localhost:4000).

## Como rodar sem Docker (opcional)

Caso prefira rodar diretamente na máquina hospedeira:
1. Instale o Java 21 JRE (`java -version`).
2. Instale o `firebase-tools`:
   ```bash
   npm install -g firebase-tools@15.34.0
   ```
3. Na raiz do repositório:
   ```bash
   firebase emulators:start --only auth,firestore,storage --project demo-habilita
   ```
