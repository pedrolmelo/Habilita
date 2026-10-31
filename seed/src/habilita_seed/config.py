"""Configurações e trava de segurança para o seed do Habilita."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

# Constante de senha de demonstração exclusivamente para o ambiente emulado local.
# NUNCA utilizar esta senha fora dos emuladores locais.
SENHA_EMULADOR_PADRAO: str = "SenhaDemo123!"

# Hosts locais expressamente permitidos para conexão dos emuladores e serviços locais.
HOSTS_LOCAIS_PERMITIDOS: frozenset[str] = frozenset(
    {"localhost", "127.0.0.1", "emulators", "storage"}
)

# Chave local service_role padrão para desenvolvimento/testes
SUPABASE_SERVICE_KEY_PADRAO: str = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwK"
    "ICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ."
    "DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q"
)


class TravaEmuladorError(RuntimeError):
    """Exceção levantada quando as condições de segurança do emulador são violadas."""


@dataclass(frozen=True)
class SeedConfig:
    """Configurações validadas do seed para execução contra serviços locais."""

    project_id: str
    auth_emulator_host: str
    firestore_emulator_host: str
    storage_url: str
    storage_service_key: str
    storage_bucket: str = "documentos"
    cpf_hmac_key: str = "demo-cpf-hmac-key-for-emulator-only"
    senha_padrao: str = SENHA_EMULADOR_PADRAO


def _extrair_host(host_str: str) -> str:
    """Extrai apenas a parte do hostname de strings no formato host:porta ou url."""
    valor = host_str.strip()
    if not valor:
        return ""
    if "://" in valor:
        parsed = urlparse(valor)
        return parsed.hostname or ""
    # Formato host:porta
    if ":" in valor:
        return valor.split(":", 1)[0]
    return valor


def validar_trava_emulador() -> SeedConfig:
    """Abre ou aborta a execução do seed verificando rigorosamente o ambiente.

    O seed aborta antes de qualquer escrita se:
    (a) As variáveis dos emuladores de Auth, Firestore e Supabase Storage não estiverem definidas;
    (b) O host não for local (localhost, 127.0.0.1 ou os serviços do Compose:
        'emulators', 'storage');
    (c) O ID do projeto não começar com o prefixo obrigatório 'demo-';
    (d) GOOGLE_APPLICATION_CREDENTIALS estiver definida (impede uso acidental de credenciais reais).
    """
    # (d) GOOGLE_APPLICATION_CREDENTIALS definida
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        raise TravaEmuladorError(
            "TRAVA DE SEGURANÇA: GOOGLE_APPLICATION_CREDENTIALS está definida no ambiente. "
            "O seed nunca aceita credenciais reais nem acessa a nuvem do Google Cloud. "
            "Remova essa variável para executar contra os emuladores locais."
        )

    # (a) Checagem de existência das variáveis de emuladores
    auth_host = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
    if not auth_host:
        raise TravaEmuladorError(
            "TRAVA DE SEGURANÇA: FIREBASE_AUTH_EMULATOR_HOST não está definida. "
            "O seed só pode rodar conectado ao emulador de Auth local."
        )

    firestore_host = os.environ.get("FIRESTORE_EMULATOR_HOST", "").strip()
    if not firestore_host:
        raise TravaEmuladorError(
            "TRAVA DE SEGURANÇA: FIRESTORE_EMULATOR_HOST não está definida. "
            "O seed só pode rodar conectado ao emulador de Firestore local."
        )

    # Supabase Storage URL
    storage_url = (
        os.environ.get("STORAGE_URL", "").strip()
        or os.environ.get("STORAGE_EMULATOR_HOST", "").strip()
        or "http://storage:5000"
    )

    # (b) Validação de hosts locais
    auth_hostname = _extrair_host(auth_host)
    if auth_hostname not in HOSTS_LOCAIS_PERMITIDOS:
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: Host do Auth inválido ou não-local: '{auth_hostname}'. "
            f"Permitidos apenas: {sorted(HOSTS_LOCAIS_PERMITIDOS)}."
        )

    firestore_hostname = _extrair_host(firestore_host)
    if firestore_hostname not in HOSTS_LOCAIS_PERMITIDOS:
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: Host do Firestore inválido: '{firestore_hostname}'. "
            f"Permitidos apenas: {sorted(HOSTS_LOCAIS_PERMITIDOS)}."
        )

    storage_hostname = _extrair_host(storage_url)
    if storage_hostname not in HOSTS_LOCAIS_PERMITIDOS:
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: Host do Storage inválido: '{storage_hostname}'. "
            f"Permitidos apenas: {sorted(HOSTS_LOCAIS_PERMITIDOS)}."
        )

    # (c) Prefixo do ID do projeto
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip() or "demo-habilita"

    if not project_id.startswith("demo-"):
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: O ID do projeto '{project_id}' não começa com 'demo-'. "
            "Emuladores do Firebase exigem o prefixo 'demo-' para operar "
            "sem autenticação de nuvem."
        )

    storage_bucket = (
        os.environ.get("STORAGE_BUCKET", "").strip()
        or os.environ.get("STORAGE_BUCKET_NAME", "").strip()
        or "documentos"
    )

    storage_service_key = (
        os.environ.get("STORAGE_SERVICE_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        or SUPABASE_SERVICE_KEY_PADRAO
    )

    # Chave de HMAC do CPF: valor padrão de desenvolvimento se não fornecido.
    # Em produção, a chave deve vir de variáveis de ambiente protegidas
    # (GitHub Secrets e variáveis do Render).
    env_hmac_key = os.environ.get("CPF_HMAC_KEY", "").strip()
    cpf_hmac_key = env_hmac_key or "demo-cpf-hmac-key-for-emulator-only"

    return SeedConfig(
        project_id=project_id,
        auth_emulator_host=auth_host,
        firestore_emulator_host=firestore_host,
        storage_url=storage_url,
        storage_service_key=storage_service_key,
        storage_bucket=storage_bucket,
        cpf_hmac_key=cpf_hmac_key,
    )
