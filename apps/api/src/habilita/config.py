"""Configuração da aplicação, lida de variáveis de ambiente.

Os valores padrão servem para o ambiente local. Se algum valor for inválido
(por exemplo PORT=abc), a aplicação falha ao iniciar, em vez de rodar errada.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chave pública demo padrão do Supabase local (iss "supabase-demo")
CHAVE_DEMO_SUPABASE: str = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwK"
    "ICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ."
    "DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", frozen=True)

    # Ambiente em que a API roda (APP_ENV).
    app_env: Literal["local", "ci", "prod"] = "local"
    # Nível de detalhe dos logs (LOG_LEVEL). Logs nunca devem ter dados pessoais.
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    # Porta em que a API escuta (PORT). O Render e a execução local definem PORT.
    port: int = Field(default=8000, ge=1, le=65535)
    # ID do projeto Firebase (FIREBASE_PROJECT_ID). `demo-` roda só nos emuladores.
    firebase_project_id: str = Field(default="demo-habilita", min_length=1, max_length=64)

    # Supabase Storage (Plano Custo Zero - ADR 0006 e ADR 0010)
    # URL interna da API de Storage (no Compose é http://storage:5000, em prod é a URL do Supabase)
    storage_url: str = Field(default="http://storage:5000", min_length=1)
    # URL pública usada pelos clientes/navegador (no Compose é http://127.0.0.1:5000)
    storage_public_url: str = Field(default="http://127.0.0.1:5000", min_length=1)
    # Nome do bucket privado de documentos
    storage_bucket: str = Field(default="documentos", min_length=1)
    # Chave service_role (SecretStr). Em prod, deve ser fornecida via ambiente e nunca ser a demo.
    supabase_service_key: SecretStr = Field(default=SecretStr(""))

    @model_validator(mode="after")
    def validar_segredos_em_prod(self) -> Settings:
        """Garante que segredos obrigatórios não estejam vazios ou com chaves demo em produção."""
        if self.app_env == "prod":
            chave = self.supabase_service_key.get_secret_value().strip()
            if not chave or chave == CHAVE_DEMO_SUPABASE:
                raise ValueError(
                    "Em produção (APP_ENV=prod), SUPABASE_SERVICE_KEY é obrigatória "
                    "e não pode usar a chave demo."
                )
        return self


def get_settings() -> Settings:
    return Settings()
