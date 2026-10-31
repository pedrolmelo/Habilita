"""Cria a aplicação FastAPI e registra as rotas."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from habilita.config import get_settings
from habilita.saude.rotas import router as saude_router


def create_app() -> FastAPI:
    # Lê e valida a configuração já na inicialização: se for inválida, a API não sobe.
    settings = get_settings()
    app = FastAPI(title="Habilita API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
    )

    app.include_router(saude_router)
    return app


app = create_app()
