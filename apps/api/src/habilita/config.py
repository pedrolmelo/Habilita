"""Configuração da aplicação, lida de variáveis de ambiente.

Os valores padrão servem para o ambiente local. Se algum valor for inválido
(por exemplo PORT=abc), a aplicação falha ao iniciar, em vez de rodar errada.
"""

from typing import Literal

from pydantic import Field, field_validator
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

    # Origens permitidas para CORS (CORS_ORIGINS)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                import json

                return list(json.loads(v))
            return [origem.strip() for origem in v.split(",") if origem.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []


def get_settings() -> Settings:
    return Settings()
