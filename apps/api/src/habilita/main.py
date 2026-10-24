"""Cria a aplicação FastAPI e registra as rotas e middlewares."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from habilita.comum.erros import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from habilita.config import get_settings
from habilita.saude.rotas import router as saude_router


def create_app() -> FastAPI:
    # Lê e valida a configuração já na inicialização: se for inválida, a API não sobe.
    get_settings()
    app = FastAPI(
        title="Habilita API",
        version="0.2.0",
        description="API de conformidade documental de SST multi-tenant",
    )

    # Middleware global para X-Request-Id (RFC e rastreabilidade)
    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        return response

    # Registro padronizado de erros Problem Details (RFC 9457)
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

    # Registro de rotas
    app.include_router(saude_router)

    return app


app = create_app()
