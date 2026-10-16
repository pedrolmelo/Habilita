"""Cria a aplicação FastAPI e registra as rotas."""

from fastapi import FastAPI

from habilita.config import get_settings
from habilita.saude.rotas import router as saude_router


def create_app() -> FastAPI:
    # Lê e valida a configuração já na inicialização: se for inválida, a API não sobe.
    get_settings()
    app = FastAPI(title="Habilita API")
    app.include_router(saude_router)
    return app


app = create_app()
