"""Rotas FastAPI para Trabalhadores e Documentos (Jornadas J2 e J3).

Conforme o contrato OpenAPI e ADR 0002/0008:
- Validação estrita de papéis e tenant.
- Upload de documentos com validação por assinatura de bytes (PDF, JPEG, PNG até 10 MiB).
- Fila de revisão de documentos (aprovação e rejeição com motivo obrigatório).
- URL assinada temporária para visualização.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from habilita.cadastros.schemas import Pagina
from habilita.comum.auth import UsuarioAutenticado, exigir_papeis
from habilita.comum.erros import (
    acesso_proibido,
    recurso_nao_encontrado,
    requisicao_invalida,
)
from habilita.trabalhadores.repositorio import TrabalhadoresRepositorio
from habilita.trabalhadores.schemas import (
    Alocacao,
    ArquivoMetadados,
    Documento,
    NovaAlocacao,
    NovoTrabalhador,
    RejeitarDocumentoPayload,
    Trabalhador,
    TrabalhadorDetalhe,
    UrlDownloadResponse,
)

router = APIRouter()


def obter_repositorio(
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> TrabalhadoresRepositorio:
    """Injeta o repositório instanciado com o tenantId seguro da claim."""
    return TrabalhadoresRepositorio(tenant_id=usuario.tenant_id)


# -----------------------------------------------------------------------------
# Trabalhadores (J2)
# -----------------------------------------------------------------------------
@router.get(
    "/trabalhadores",
    response_model=Pagina[Trabalhador],
    tags=["Trabalhadores"],
    summary="Listar trabalhadores",
)
def listar_trabalhadores(
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> Pagina[Trabalhador]:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    itens, proximo = repo.listar_trabalhadores(
        terceirizada_id_filtro=filtro_terceirizada,
        limite=limite,
        cursor=cursor,
    )
    return Pagina(itens=itens, proximoCursor=proximo)


@router.post(
    "/trabalhadores",
    response_model=Trabalhador,
    status_code=status.HTTP_201_CREATED,
    tags=["Trabalhadores"],
    summary="Cadastrar trabalhador",
)
def cadastrar_trabalhador(
    payload: NovoTrabalhador,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> Trabalhador:
    if usuario.papel == "terceirizada":
        if not usuario.terceirizada_id:
            raise acesso_proibido("Usuário terceirizada sem terceirizadaId vinculado.")
        terceirizada_id = usuario.terceirizada_id
    else:
        if not payload.terceirizadaId:
            raise requisicao_invalida("Campo 'terceirizadaId' é obrigatório para gestores.")
        terceirizada_id = payload.terceirizadaId

    return repo.criar_trabalhador(
        nome=payload.nome,
        cpf=payload.cpf,
        terceirizada_id=terceirizada_id,
    )


@router.get(
    "/trabalhadores/{trabalhador_id}",
    response_model=TrabalhadorDetalhe,
    tags=["Trabalhadores"],
    summary="Detalhar trabalhador com documentos e semáforo",
)
def detalhar_trabalhador(
    trabalhador_id: str,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> TrabalhadorDetalhe:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    trb = repo.obter_trabalhador(
        trabalhador_id=trabalhador_id,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not trb:
        raise recurso_nao_encontrado(
            f"Trabalhador '{trabalhador_id}' não encontrado ou fora do escopo."
        )
    return trb


@router.post(
    "/contratos/{contrato_id}/alocacoes",
    response_model=Alocacao,
    status_code=status.HTTP_201_CREATED,
    tags=["Trabalhadores"],
    summary="Vincular trabalhador ao contrato",
)
def vincular_trabalhador_contrato(
    contrato_id: str,
    payload: NovaAlocacao,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> Alocacao:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    trb = repo.obter_trabalhador(
        trabalhador_id=payload.trabalhadorId,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not trb:
        raise recurso_nao_encontrado(f"Trabalhador '{payload.trabalhadorId}' não encontrado.")

    return repo.vincular_alocacao(
        contrato_id=contrato_id,
        trabalhador_id=payload.trabalhadorId,
    )


# -----------------------------------------------------------------------------
# Documentos (J2 e J3)
# -----------------------------------------------------------------------------
def detectar_content_type(cabecalho_bytes: bytes) -> str | None:
    """Detecta o MIME type pela assinatura mágica dos bytes (AGENTS.md)."""
    if cabecalho_bytes.startswith(b"%PDF"):
        return "application/pdf"
    if cabecalho_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if cabecalho_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


@router.post(
    "/trabalhadores/{trabalhador_id}/documentos",
    response_model=Documento,
    status_code=status.HTTP_201_CREATED,
    tags=["Documentos"],
    summary="Enviar documento (upload)",
)
async def enviar_documento(
    trabalhador_id: str,
    arquivo: Annotated[UploadFile, File()],
    tipoDocumentoId: Annotated[str, Form()],
    validoAte: Annotated[str, Form()],
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("terceirizada", "gestor"))],
    dataEmissao: Annotated[str | None, Form()] = None,
) -> Documento:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    trb = repo.obter_trabalhador(
        trabalhador_id=trabalhador_id,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not trb:
        raise recurso_nao_encontrado(
            f"Trabalhador '{trabalhador_id}' não encontrado ou fora do escopo."
        )

    conteudo = await arquivo.read()
    tamanho = len(conteudo)
    if tamanho == 0:
        raise requisicao_invalida("Arquivo enviado está vazio.")
    if tamanho > 10 * 1024 * 1024:
        raise requisicao_invalida("Tamanho do arquivo excede o limite máximo de 10 MiB.")

    content_type = detectar_content_type(conteudo[:16])
    if not content_type:
        raise requisicao_invalida(
            "Tipo de arquivo não permitido. Apenas PDF, JPEG e PNG são aceitos."
        )

    sha256_hash = hashlib.sha256(conteudo).hexdigest()
    arquivo_meta = ArquivoMetadados(
        contentType=content_type,  # type: ignore[arg-type]
        tamanhoBytes=tamanho,
        sha256=sha256_hash,
    )

    return repo.criar_documento(
        trabalhador_id=trabalhador_id,
        tipo_documento_id=tipoDocumentoId,
        valido_ate=validoAte,
        data_emissao=dataEmissao,
        arquivo_meta=arquivo_meta,
    )


@router.get(
    "/documentos",
    response_model=Pagina[Documento],
    tags=["Documentos"],
    summary="Listar documentos (fila de revisão)",
)
def listar_documentos(
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
    statusRevisao: Annotated[str | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> Pagina[Documento]:
    itens, proximo = repo.listar_documentos(
        status_revisao=statusRevisao,
        limite=limite,
        cursor=cursor,
    )
    return Pagina(itens=itens, proximoCursor=proximo)


@router.get(
    "/documentos/{documento_id}",
    response_model=Documento,
    tags=["Documentos"],
    summary="Detalhar documento",
)
def detalhar_documento(
    documento_id: str,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> Documento:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    doc = repo.obter_documento(
        documento_id=documento_id,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not doc:
        raise recurso_nao_encontrado(
            f"Documento '{documento_id}' não encontrado ou fora do escopo."
        )
    return doc


@router.post(
    "/documentos/{documento_id}/url-download",
    response_model=UrlDownloadResponse,
    tags=["Documentos"],
    summary="Gerar link temporário para visualizar o arquivo",
)
def gerar_url_download(
    documento_id: str,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor", "terceirizada"))],
) -> UrlDownloadResponse:
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    resp = repo.gerar_url_download(
        documento_id=documento_id,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not resp:
        raise recurso_nao_encontrado(
            f"Documento '{documento_id}' não encontrado ou fora do escopo."
        )
    return resp


@router.post(
    "/documentos/{documento_id}/aprovacao",
    response_model=Documento,
    tags=["Documentos"],
    summary="Aprovar documento",
)
def aprovar_documento(
    documento_id: str,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> Documento:
    doc = repo.aprovar_documento(documento_id)
    if not doc:
        raise recurso_nao_encontrado(f"Documento '{documento_id}' não encontrado.")
    return doc


@router.post(
    "/documentos/{documento_id}/rejeicao",
    response_model=Documento,
    tags=["Documentos"],
    summary="Rejeitar documento com motivo obrigatório",
)
def rejeitar_documento(
    documento_id: str,
    payload: RejeitarDocumentoPayload,
    repo: Annotated[TrabalhadoresRepositorio, Depends(obter_repositorio)],
    usuario: Annotated[UsuarioAutenticado, Depends(exigir_papeis("gestor"))],
) -> Documento:
    doc = repo.rejeitar_documento(documento_id, motivo=payload.motivo)
    if not doc:
        raise recurso_nao_encontrado(f"Documento '{documento_id}' não encontrado.")
    return doc
