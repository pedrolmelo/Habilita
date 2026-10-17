# apps/web — Frontend do Habilita

Interface web do Habilita desenvolvida com React, TypeScript (modo `strict`) e Vite.

Em produção, os arquivos compilados (`dist/`) são estáticos e hospedados no Firebase Hosting (não existe contêiner Docker de produção para o frontend).

## Como rodar com Docker (recomendado)

O servidor de desenvolvimento do Vite sobe automaticamente via Compose:

```bash
docker compose up -d web
```

Acesse em: [http://localhost:5173](http://localhost:5173).

- O código em `src/` é montado em modo leitura e reflete as alterações na tela na hora (Hot Module Replacement).
- As chamadas para `/api/*` passam pelo proxy do Vite e são direcionadas internamente para `http://api:8000/*`.
- As dependências (`node_modules`) ficam isoladas dentro da imagem e não são sobrescritas pelo volume local.

> **Dica para o VS Code / editor:** Para ter autocompletar e tipagem no editor sem precisar de Node na sua máquina hospedeira, a pasta `apps/web/node_modules/` pode ser sincronizada a partir do contêiner:
>
> ```bash
> docker run --rm -v "$PWD/apps/web":/host habilita-web:dev cp -rp /app/node_modules /host/
> ```

Para rodar verificações de qualidade dentro do contêiner:

```bash
docker compose exec web sh -c "npm run lint && npm run typecheck && npm run format:check && npm run build"
```

## Como rodar sem Docker (opcional)

Pré-requisitos: Node.js 24 LTS e `npm`.

1. Instale as dependências:

   ```bash
   npm ci
   ```

2. Se a API estiver rodando localmente (seja no Docker ou na sua máquina na porta 8000), defina o destino do proxy:

   ```bash
   export API_PROXY_TARGET=http://localhost:8000
   npm run dev
   ```

3. Scripts de verificação e build:
   ```bash
   npm run lint          # ESLint (flat config com typescript-eslint, proibido any)
   npm run typecheck     # Checagem rigorosa de tipos TypeScript (tsc --noEmit)
   npm run format:check  # Verificação de estilo com Prettier
   npm run format        # Formatação automática de código com Prettier
   npm run build         # Build estático de produção
   ```
