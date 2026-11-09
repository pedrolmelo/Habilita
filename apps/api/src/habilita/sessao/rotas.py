"""Rotas de sessão do usuário autenticado."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from habilita.comum.auth import UsuarioAutenticado, extrair_usuario

router = APIRouter(tags=["Sessão"])


class PerfilResponse(BaseModel):
    """Perfil do usuário autenticado extraído das claims do token."""

    model_config = ConfigDict(extra="forbid")

    uid: str
    tenantId: str
    papel: str
    terceirizadaId: str | None = None


@router.get("/me", response_model=PerfilResponse, operation_id="obterPerfil")
def obter_perfil(
    usuario: Annotated[UsuarioAutenticado, Depends(extrair_usuario)],
) -> PerfilResponse:
    """Perfil do usuário autenticado extraído com base nas custom claims."""
    return PerfilResponse(
        uid=usuario.uid,
        tenantId=usuario.tenant_id,
        papel=usuario.papel,
        terceirizadaId=usuario.terceirizada_id,
    )
