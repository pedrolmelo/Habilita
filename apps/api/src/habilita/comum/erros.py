"""Modelos e handlers para erros no padrão Problem Details (RFC 9457).

Conforme o contrato da API e a ADR 0002, todas as respostas de erro retornam
Content-Type 'application/problem+json' com a estrutura padronizada.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErroValidacaoCampo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campo: str
    mensagem: str


class Problema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="about:blank", description="URI do tipo do problema")
    title: str = Field(description="Título curto e legível do erro")
    status: int = Field(description="Código HTTP correspondente")
    detail: str | None = Field(default=None, description="Explicação detalhada do erro")
    instance: str | None = Field(default=None, description="URI da requisição que gerou o erro")
    requestId: str | None = Field(
        default=None, description="Identificador único para correlação de logs"
    )
    erros: list[ErroValidacaoCampo] | None = Field(
        default=None, description="Lista de erros de validação por campo"
    )


class AppException(Exception):
    """Exceção base da aplicação para respostas no formato Problem Details."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str | None = None,
        type_: str = "about:blank",
        erros: list[ErroValidacaoCampo] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_ = type_
        self.erros = erros
        super().__init__(detail or title)


def recurso_nao_encontrado(
    detail: str = "Recurso não encontrado ou fora do escopo do usuário.",
) -> AppException:
    return AppException(
        status_code=404,
        title="Não encontrado",
        detail=detail,
    )


def acesso_proibido(
    detail: str = "Papel sem permissão para esta rota.",
) -> AppException:
    return AppException(
        status_code=403,
        title="Acesso proibido",
        detail=detail,
    )


def nao_autenticado(
    detail: str = "Credenciais de autenticação ausentes ou inválidas.",
) -> AppException:
    return AppException(
        status_code=401,
        title="Não autenticado",
        detail=detail,
    )


def requisicao_invalida(
    detail: str = "Dados da requisição inválidos.",
    erros: list[ErroValidacaoCampo] | None = None,
) -> AppException:
    return AppException(
        status_code=400,
        title="Requisição inválida",
        detail=detail,
        erros=erros,
    )


def extrair_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-Id")


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = extrair_request_id(request)
    problema = Problema(
        type=exc.type_,
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
        requestId=request_id,
        erros=exc.erros,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problema.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers={"X-Request-Id": request_id} if request_id else {},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = extrair_request_id(request)
    title_map = {
        400: "Requisição inválida",
        401: "Não autenticado",
        403: "Acesso proibido",
        404: "Não encontrado",
        405: "Método não permitido",
        422: "Entidade improcessável",
        500: "Erro interno do servidor",
    }
    title = title_map.get(exc.status_code, "Erro")
    detail = str(exc.detail) if exc.detail else title

    problema = Problema(
        type="about:blank",
        title=title,
        status=exc.status_code,
        detail=detail,
        instance=str(request.url.path),
        requestId=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problema.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers={"X-Request-Id": request_id} if request_id else {},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = extrair_request_id(request)
    erros: list[ErroValidacaoCampo] = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
        campo = ".".join(loc) or "corpo"
        mensagem = err.get("msg", "Valor inválido")
        erros.append(ErroValidacaoCampo(campo=campo, mensagem=mensagem))

    problema = Problema(
        type="about:blank",
        title="Erro de validação",
        status=422,
        detail="Os dados enviados contêm erros de validação.",
        instance=str(request.url.path),
        requestId=request_id,
        erros=erros if erros else None,
    )
    return JSONResponse(
        status_code=422,
        content=problema.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers={"X-Request-Id": request_id} if request_id else {},
    )
