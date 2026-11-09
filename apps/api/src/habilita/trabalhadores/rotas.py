"""Rotas FastAPI para Trabalhadores e Documentos (Jornadas J2 e J3).

Conforme o contrato OpenAPI e ADR 0002/0006/0008:
- Validação estrita de papéis e tenant.
- Upload de documentos com validação por assinatura de bytes (PDF e JPEG até 5.000.000 bytes).
- Limite excedido retorna 413; tipo inválido retorna 415.
- Fila de revisão de documentos (aprovação e rejeição com motivo mínimo de 10 caracteres).
- Transições de revisão permitidas apenas para documentos com status PENDENTE (409 em conflito).
- URL assinada temporária para visualização.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from habilita.cadastros.repositorio import CadastrosRepositorio
from habilita.cadastros.schemas import Pagina
from habilita.comum.auth import UsuarioAutenticado, exigir_papeis, extrair_usuario
from habilita.comum.erros import (
    acesso_proibido,
    entidade_muito_grande,
    recurso_nao_encontrado,
    requisicao_invalida,
    tipo_midia_nao_suportado,
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

MAX_UPLOAD_BYTES = 5_000_000


def obter_repositorio(
    usuario: Annotated[UsuarioAutenticado, Depends(extrair_usuario)],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
) -> Trabalhador:
    if usuario.papel == "terceirizada":
        if not usuario.terceirizada_id:
            raise acesso_proibido("Usuário terceirizada sem terceirizadaId vinculado.")
        terceirizada_id = usuario.terceirizada_id
    else:
        if not payload.terceirizadaId:
            raise requisicao_invalida(
                "Campo 'terceirizadaId' é obrigatório para administradores e analistas."
            )
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "terceirizada")),
    ],
) -> Alocacao:
    cad_repo = CadastrosRepositorio(tenant_id=usuario.tenant_id)
    filtro_terceirizada = usuario.terceirizada_id if usuario.papel == "terceirizada" else None
    contrato = cad_repo.obter_contrato(
        contrato_id=contrato_id, terceirizada_id_filtro=filtro_terceirizada
    )
    if not contrato:
        raise recurso_nao_encontrado(f"Contrato '{contrato_id}' não encontrado ou fora do escopo.")

    trb = repo.obter_trabalhador(
        trabalhador_id=payload.trabalhadorId,
        terceirizada_id_filtro=filtro_terceirizada,
    )
    if not trb:
        raise recurso_nao_encontrado(f"Trabalhador '{payload.trabalhadorId}' não encontrado.")

    if trb.terceirizadaId != contrato.terceirizadaId:
        raise requisicao_invalida("Trabalhador pertence a uma terceirizada distinta do contrato.")

    return repo.vincular_alocacao(
        contrato_id=contrato_id,
        trabalhador_id=payload.trabalhadorId,
    )


# -----------------------------------------------------------------------------
# Documentos (J2 e J3)
# -----------------------------------------------------------------------------
def detectar_content_type(
    cabecalho_bytes: bytes,
) -> Literal["application/pdf", "image/jpeg"] | None:
    """Detecta o MIME type pela assinatura mágica dos bytes (PDF e JPEG conforme ADR 0006)."""
    if cabecalho_bytes.startswith(b"%PDF"):
        return "application/pdf"
    if cabecalho_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
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

    cad_repo = CadastrosRepositorio(tenant_id=usuario.tenant_id)
    if not cad_repo.obter_tipo_documento(tipoDocumentoId):
        raise recurso_nao_encontrado(
            f"Tipo de documento '{tipoDocumentoId}' não encontrado no tenant."
        )

    conteudo = await arquivo.read()
    tamanho = len(conteudo)
    if tamanho == 0:
        raise requisicao_invalida("Arquivo enviado está vazio.")
    if tamanho > MAX_UPLOAD_BYTES:
        raise entidade_muito_grande(
            f"O arquivo excede o limite máximo permitido de {MAX_UPLOAD_BYTES} bytes."
        )

    content_type = detectar_content_type(conteudo[:16])
    if not content_type:
        raise tipo_midia_nao_suportado(
            "Tipo de arquivo não permitido. Apenas PDF e JPEG são aceitos."
        )

    sha256_hash = hashlib.sha256(conteudo).hexdigest()
    arquivo_meta = ArquivoMetadados(
        contentType=content_type,
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst")),
    ],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst", "terceirizada")),
    ],
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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst")),
    ],
) -> Documento:
    return repo.aprovar_documento(documento_id)


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
    usuario: Annotated[
        UsuarioAutenticado,
        Depends(exigir_papeis("admin_contratante", "analista_sst")),
    ],
) -> Documento:
    return repo.rejeitar_documento(documento_id, motivo=payload.motivo)
