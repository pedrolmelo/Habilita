"""Configuração da aplicação, lida de variáveis de ambiente.

Os valores padrão servem para o ambiente local. Se algum valor for inválido
(por exemplo PORT=abc), a aplicação falha ao iniciar, em vez de rodar errada.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Supabase Storage (Plano Custo Zero)
    # URL interna da API de Storage (no Compose é http://storage:5000, em prod é a URL do Supabase)
    storage_url: str = Field(default="http://storage:5000", min_length=1)
    # URL pública usada pelos clientes/navegador (no Compose é http://127.0.0.1:5000)
    storage_public_url: str = Field(default="http://127.0.0.1:5000", min_length=1)
    # Nome do bucket privado de documentos
    storage_bucket: str = Field(default="documentos", min_length=1)
    # Chaves JWT do Supabase Storage (valores dummy para desenvolvimento local)
    supabase_service_key: str = Field(
        default=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwK"
            "ICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ."
            "DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q"
        ),
        min_length=1,
    )
    supabase_anon_key: str = Field(
        default=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwK"
            "ICAgICJleHAiOiAxNzk5NTM1NjAwCn0."
            "dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"
        ),
        min_length=1,
    )


def get_settings() -> Settings:
    return Settings()
