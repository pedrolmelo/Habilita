#!/bin/sh
# infra/storage/init-bucket.sh
# Inicialização idempotente do bucket privado no Supabase Storage.
# Executado uma única vez na subida do Docker Compose pelo serviço storage-init.
set -eu

URL="${STORAGE_URL:-http://storage:5000}"
KEY="${STORAGE_SERVICE_KEY}"
BUCKET="${STORAGE_BUCKET:-documentos}"
MAX_BYTES="${STORAGE_MAX_BYTES:-5242880}"
MIME_TYPES="${STORAGE_ALLOWED_MIME:-application/pdf,image/jpeg}"

# Formata a lista separada por vírgula em array JSON: ["application/pdf","image/jpeg"]
MIME_JSON=$(echo "$MIME_TYPES" | awk -F',' '{
  printf "["
  for(i=1; i<=NF; i++) {
    printf "\"%s\"", $i
    if (i < NF) printf ","
  }
  printf "]"
}')

echo "==> [storage-init] Verificando existência do bucket '$BUCKET' no Supabase Storage..."
status_code=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $KEY" \
  "$URL/bucket/$BUCKET")

if [ "$status_code" = "200" ]; then
  echo "==> [storage-init] Bucket '$BUCKET' já existe. Nenhuma ação necessária."
  exit 0
fi

echo "==> [storage-init] Bucket '$BUCKET' não encontrado (HTTP $status_code). Criando bucket privado..."
res=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"$BUCKET\", \"name\": \"$BUCKET\", \"public\": false, \"file_size_limit\": $MAX_BYTES, \"allowed_mime_types\": $MIME_JSON}" \
  "$URL/bucket")

http_code=$(echo "$res" | tail -n 1)
body=$(echo "$res" | sed '$d')

if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
  echo "==> [storage-init] Bucket '$BUCKET' criado com sucesso!"
  exit 0
elif echo "$body" | grep -q "already exists"; then
  echo "==> [storage-init] Bucket '$BUCKET' já existe (criado concorrentemente)."
  exit 0
else
  echo "==> [storage-init] ERRO ao criar bucket '$BUCKET' (HTTP $http_code): $body"
  exit 1
fi
