"""Configurações e trava de segurança para o seed do Habilita."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

# Constante de senha de demonstração exclusivamente para o ambiente emulado local.
# NUNCA utilizar esta senha fora dos emuladores locais.
SENHA_EMULADOR_PADRAO: str = "SenhaDemo123!"

# Hosts locais expressamente permitidos para conexão dos emuladores.
HOSTS_LOCAIS_PERMITIDOS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "emulators"})


class TravaEmuladorError(RuntimeError):
    """Exceção levantada quando as condições de segurança do emulador são violadas."""


@dataclass(frozen=True)
class SeedConfig:
    """Configurações validadas do seed para execução contra emuladores."""

    project_id: str
    auth_emulator_host: str
    firestore_emulator_host: str
    storage_emulator_host: str
    storage_bucket: str
    cpf_hmac_key: str
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
    (a) As variáveis dos emuladores de Auth, Firestore e Storage não estiverem definidas;
    (b) O host não for local (localhost, 127.0.0.1 ou o nome do serviço do Compose: 'emulators');
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

    storage_host = (
        os.environ.get("FIREBASE_STORAGE_EMULATOR_HOST", "").strip()
        or os.environ.get("STORAGE_EMULATOR_HOST", "").strip()
    )
    if not storage_host:
        raise TravaEmuladorError(
            "TRAVA DE SEGURANÇA: Nenhuma variável de emulador de Storage "
            "(FIREBASE_STORAGE_EMULATOR_HOST ou STORAGE_EMULATOR_HOST) está definida. "
            "O seed só pode rodar conectado ao emulador de Cloud Storage local."
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

    storage_hostname = _extrair_host(storage_host)
    if storage_hostname not in HOSTS_LOCAIS_PERMITIDOS:
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: Host do Storage inválido: '{storage_hostname}'. "
            f"Permitidos apenas: {sorted(HOSTS_LOCAIS_PERMITIDOS)}."
        )

    # (c) Prefixo do ID do projeto
    project_id = (
        os.environ.get("FIREBASE_PROJECT_ID", "").strip()
        or os.environ.get("GCLOUD_PROJECT", "").strip()
    )
    if not project_id:
        project_id = "demo-habilita"

    if not project_id.startswith("demo-"):
        raise TravaEmuladorError(
            f"TRAVA DE SEGURANÇA: O ID do projeto '{project_id}' não começa com 'demo-'. "
            "Emuladores do Firebase exigem o prefixo 'demo-' para operar sem autenticação de nuvem."
        )

    env_bucket = os.environ.get("STORAGE_BUCKET_NAME", "").strip()
    storage_bucket = env_bucket or f"{project_id}.appspot.com"

    # Chave de HMAC do CPF: valor padrão de desenvolvimento se não fornecido.
    # Em produção, a chave deve vir do Google Cloud Secret Manager conforme ADR 0008.
    env_hmac_key = os.environ.get("CPF_HMAC_KEY", "").strip()
    cpf_hmac_key = env_hmac_key or "demo-cpf-hmac-key-for-emulator-only"

    # Normalizar ambas as variáveis de Storage no os.environ para que tanto o Firebase Admin SDK
    # quanto o google-cloud-storage funcionem sem atrito
    if "://" not in storage_host:
        os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = storage_host
        os.environ["STORAGE_EMULATOR_HOST"] = f"http://{storage_host}"
    else:
        os.environ["STORAGE_EMULATOR_HOST"] = storage_host
        parsed_storage = urlparse(storage_host)
        os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = (
            f"{parsed_storage.hostname}:{parsed_storage.port}"
            if parsed_storage.port
            else parsed_storage.hostname or ""
        )

    return SeedConfig(
        project_id=project_id,
        auth_emulator_host=auth_host,
        firestore_emulator_host=firestore_host,
        storage_emulator_host=storage_host,
        storage_bucket=storage_bucket,
        cpf_hmac_key=cpf_hmac_key,
    )
