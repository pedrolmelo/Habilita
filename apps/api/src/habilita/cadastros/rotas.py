"""Rotas FastAPI para a Jornada J1 (Contratos e Cadastros).

Conforme o contrato da API:
- Autenticação obrigatória com verificação de papéis.
- Isolamento estrito de tenant (recurso fora do tenant retorna 404).
- Respostas de erro padronizadas em RFC 9457 (Problem Details).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from habilita.cadastros.repositorio import CadastrosRepositorio
from habilita.cadastros.schemas import (
    Contrato,
    ListaTiposDocumento,
    NovaTerceirizada,
    NovoContrato,
    NovoTipoDocumento,
    Pagina,
    SubstituirExigencias,
    Terceirizada,
    TipoDocumento,
)
from habilita.comum.auth import UsuarioAutenticado, exigir_papeis
from habilita.comum.erros import recurso_nao_encontrado

router = APIRouter(tags=["Cadastros"])


def obter_repositorio(
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> CadastrosRepositorio:
    """Injeta o repositório instanciado com o tenantId seguro da claim."""
    return CadastrosRepositorio(tenant_id=usuario.tenant_id)


# -----------------------------------------------------------------------------
# Terceirizadas
# -----------------------------------------------------------------------------
@router.get(
    "/terceirizadas",
    response_model=Pagina[Terceirizada],
    summary="Listar terceirizadas do tenant",
)
def listar_terceirizadas(
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> Pagina[Terceirizada]:
    itens, proximo = repo.listar_terceirizadas(limite=limite, cursor=cursor)
    return Pagina(itens=itens, proximoCursor=proximo)


@router.post(
    "/terceirizadas",
    response_model=Terceirizada,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar terceirizada",
)
def cadastrar_terceirizada(
    payload: NovaTerceirizada,
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> Terceirizada:
    return repo.criar_terceirizada(payload)


# -----------------------------------------------------------------------------
# Tipos de Documento
# -----------------------------------------------------------------------------
@router.get(
    "/tipos-documento",
    response_model=ListaTiposDocumento,
    summary="Listar tipos de documento do tenant",
)
def listar_tipos_documento(
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
) -> ListaTiposDocumento:
    itens = repo.listar_tipos_documento()
    return ListaTiposDocumento(itens=itens)


@router.post(
    "/tipos-documento",
    response_model=TipoDocumento,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar tipo de documento",
)
def cadastrar_tipo_documento(
    payload: NovoTipoDocumento,
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> TipoDocumento:
    return repo.criar_tipo_documento(payload)


# -----------------------------------------------------------------------------
# Contratos
# -----------------------------------------------------------------------------
@router.get(
    "/contratos",
    response_model=Pagina[Contrato],
    summary="Listar contratos",
)
def listar_contratos(
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> Pagina[Contrato]:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    itens, proximo = repo.listar_contratos(
        terceirizada_id_filtro=filtro_terceirizada,
        limite=limite,
        cursor=cursor,
    )
    return Pagina(itens=itens, proximoCursor=proximo)


@router.post(
    "/contratos",
    response_model=Contrato,
    status_code=status.HTTP_201_CREATED,
    summary="Criar contrato",
)
def criar_contrato(
    payload: NovoContrato,
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> Contrato:
    # Garante que a terceirizada vinculada existe no tenant do usuário
    terceirizada = repo.obter_terceirizada(payload.terceirizadaId)
    if not terceirizada:
        raise recurso_nao_encontrado(
            f"Terceirizada '{payload.terceirizadaId}' não encontrada no tenant."
        )

    return repo.criar_contrato(payload)


@router.get(
    "/contratos/{contrato_id}",
    response_model=Contrato,
    summary="Detalhar contrato",
)
def detalhar_contrato(
    contrato_id: str,
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> Contrato:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    contrato = repo.obter_contrato(
        contrato_id=contrato_id, terceirizada_id_filtro=filtro_terceirizada
    )
    if not contrato:
        raise recurso_nao_encontrado(
            f"Contrato '{contrato_id}' não encontrado ou fora do escopo do usuário."
        )
    return contrato


@router.put(
    "/contratos/{contrato_id}/exigencias",
    response_model=Contrato,
    summary="Substituir matriz de exigências do contrato",
)
def substituir_exigencias_contrato(
    contrato_id: str,
    payload: SubstituirExigencias,
    repo: Annotated[CadastrosRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> Contrato:
    # Valida que todos os tipos de documentos existem no tenant
    for tid in payload.tipoDocumentoIds:
        if not repo.obter_tipo_documento(tid):
            raise recurso_nao_encontrado(f"Tipo de documento '{tid}' não encontrado no tenant.")

    contrato = repo.substituir_exigencias(contrato_id, payload.tipoDocumentoIds)
    if not contrato:
        raise recurso_nao_encontrado(f"Contrato '{contrato_id}' não encontrado.")
    return contrato
