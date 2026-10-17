"""Definição declarativa dos cenários determinísticos de dados de demonstração."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from habilita_seed.cpf import (
    calcular_digitos_cnpj,
    calcular_digitos_cpf,
    mascarar_cpf,
)
from habilita_seed.pdf import derivar_uuid_arquivo


@dataclass(frozen=True)
class UsuarioSeed:
    uid: str
    email: str
    nome: str
    papel: str  # gestor | terceirizada | porteiro
    tenant_id: str
    terceirizada_id: str | None = None

    @property
    def custom_claims(self) -> dict[str, Any]:
        claims: dict[str, Any] = {
            "tenantId": self.tenant_id,
            "papel": self.papel,
        }
        if self.papel == "terceirizada":
            if not self.terceirizada_id:
                raise ValueError("Usuário terceirizada exige terceirizadaId nas claims.")
            claims["terceirizadaId"] = self.terceirizada_id
        return claims


@dataclass(frozen=True)
class TipoDocumentoSeed:
    id: str
    nome: str
    validade_meses: int
    ativo: bool = True


@dataclass(frozen=True)
class TerceirizadaSeed:
    id: str
    razao_social: str
    cnpj_base: str
    ativa: bool = True

    @property
    def cnpj(self) -> str:
        return calcular_digitos_cnpj(self.cnpj_base)


@dataclass(frozen=True)
class ContratoSeed:
    id: str
    identificador: str
    terceirizada_id: str
    exigencias_ids: list[str]
    offset_inicio_dias: int
    offset_fim_dias: int
    vigente: bool = True
    versao_matriz: int = 1


@dataclass(frozen=True)
class DocumentoSeed:
    id: str
    tipo_documento_id: str
    offset_valido_ate_dias: int
    offset_data_emissao_dias: int | None = None
    status_revisao: str = "APROVADO"  # PENDENTE, APROVADO, REJEITADO
    motivo_rejeicao: str | None = None
    enviado_por_uid: str | None = None
    revisado_por_uid: str | None = None


@dataclass(frozen=True)
class TrabalhadorSeed:
    id: str
    terceirizada_id: str
    nome: str
    cpf_base: str
    ativo: bool = True
    documentos: list[DocumentoSeed] = field(default_factory=list)
    contratos_alocados: list[str] = field(default_factory=list)

    @property
    def cpf(self) -> str:
        return calcular_digitos_cpf(self.cpf_base)

    @property
    def cpf_mascarado(self) -> str:
        return mascarar_cpf(self.cpf)


@dataclass(frozen=True)
class TenantSeed:
    id: str
    nome: str
    tipos_documento: list[TipoDocumentoSeed]
    terceirizadas: list[TerceirizadaSeed]
    contratos: list[ContratoSeed]
    trabalhadores: list[TrabalhadorSeed]
    usuarios: list[UsuarioSeed]


# =============================================================================
# RECALCULO DE SEMÁFORO (RN-04 a RN-07)
# TODO: Esta função de semáforo será substituída pelo recálculo do domínio quando existir.
# Risco conhecido: duplicação temporária das regras de negócio RN-04 a RN-07 no seed.
# =============================================================================


def calcular_situacao_validade(valido_ate: date, data_referencia: date) -> str:
    """Calcula a situação de validade conforme regra RN-04.

    dias = validoAte - dataReferencia
    se dias < 0 -> VENCIDO
    se 0 <= dias <= 30 -> A_VENCER
    se dias > 30 -> VALIDO
    """
    dias = (valido_ate - data_referencia).days
    if dias < 0:
        return "VENCIDO"
    if dias <= 30:
        return "A_VENCER"
    return "VALIDO"


def calcular_alocacao(
    contrato: ContratoSeed,
    trabalhador: TrabalhadorSeed,
    data_referencia: date,
    tipos_por_id: dict[str, TipoDocumentoSeed],
) -> dict[str, Any]:
    """Calcula o semáforo materializado de uma alocação (regras RN-04, RN-05, RN-06).

    Retorna o documento serializável para a subcoleção
    `tenants/{tenantId}/contratos/{contratoId}/alocacoes/{trabalhadorId}`.
    """
    pendencias: list[dict[str, Any]] = []
    situacoes_por_exigencia: list[str] = []
    datas_vencimento_atendidas: list[date] = []

    for tipo_id in contrato.exigencias_ids:
        tipo = tipos_por_id[tipo_id]
        # RN-05: Considera-se o documento APROVADO do trabalhador, daquele tipo,
        # com o maior validoAte.
        docs_aprovados = [
            doc
            for doc in trabalhador.documentos
            if doc.tipo_documento_id == tipo_id and doc.status_revisao == "APROVADO"
        ]

        if not docs_aprovados:
            # Não atende exigência
            pendencias.append(
                {
                    "tipoDocumentoId": tipo_id,
                    "tipoDocumentoNome": tipo.nome,
                    "motivo": "AUSENTE",
                    "contratoId": contrato.id,
                }
            )
            situacoes_por_exigencia.append("AUSENTE")
            continue

        # Seleciona o aprovado com maior validoAte
        doc_eleito = max(docs_aprovados, key=lambda d: d.offset_valido_ate_dias)
        valido_ate = data_referencia + timedelta(days=doc_eleito.offset_valido_ate_dias)
        datas_vencimento_atendidas.append(valido_ate)

        situacao = calcular_situacao_validade(valido_ate, data_referencia)
        situacoes_por_exigencia.append(situacao)

        if situacao == "VENCIDO":
            pendencias.append(
                {
                    "tipoDocumentoId": tipo_id,
                    "tipoDocumentoNome": tipo.nome,
                    "motivo": "VENCIDO",
                    "contratoId": contrato.id,
                }
            )

    # RN-06: Semáforo trabalhador x contrato
    # Vermelho se alguma exigência não tem documento que a atenda (AUSENTE) ou se está VENCIDO
    # Amarelo se todas são atendidas e ao menos uma está A_VENCER
    # Verde se todas estão VALIDO
    if any(s in ("AUSENTE", "VENCIDO") for s in situacoes_por_exigencia):
        semaforo = "VERMELHO"
    elif any(s == "A_VENCER" for s in situacoes_por_exigencia):
        semaforo = "AMARELO"
    else:
        semaforo = "VERDE"

    proximo_vencimento_str: str | None = None
    if datas_vencimento_atendidas:
        proximo_vencimento_str = min(datas_vencimento_atendidas).isoformat()

    return {
        "contratoId": contrato.id,
        "trabalhadorId": trabalhador.id,
        "semaforo": semaforo,
        "pendencias": pendencias,
        "proximoVencimento": proximo_vencimento_str,
        "calculadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
    }


# =============================================================================
# CONSTRUÇÃO DECLARATIVA DOS DADOS DE DEMONSTRAÇÃO
# =============================================================================


def construir_cenarios_seed() -> list[TenantSeed]:
    """Retorna os tenants Alfa e Beta com todos os dados e cenários declarativos."""
    # Tipos de documento padrão
    tdoc_aso = TipoDocumentoSeed(
        id="tdoc_aso",
        nome="Atestado de Saude Ocupacional (ASO)",
        validade_meses=12,
    )
    tdoc_nr35 = TipoDocumentoSeed(
        id="tdoc_nr35",
        nome="Certificado de Treinamento em Altura (NR-35)",
        validade_meses=24,
    )

    # -------------------------------------------------------------------------
    # TENANT ALFA
    # -------------------------------------------------------------------------
    ter_alfa_1 = TerceirizadaSeed(
        id="ter_alfa_1",
        razao_social="Alfa Manutencao e Montagens Industriais Ltda",
        cnpj_base="111111110001",
    )
    ter_alfa_2 = TerceirizadaSeed(
        id="ter_alfa_2",
        razao_social="Alfa Engenharia de Estruturas Ltda",
        cnpj_base="222222220001",
    )

    ctr_alfa_1 = ContratoSeed(
        id="ctr_alfa_1",
        identificador="CTR-ALFA-001",
        terceirizada_id="ter_alfa_1",
        exigencias_ids=["tdoc_aso", "tdoc_nr35"],
        offset_inicio_dias=-90,
        offset_fim_dias=270,
        vigente=True,
    )
    ctr_alfa_2 = ContratoSeed(
        id="ctr_alfa_2",
        identificador="CTR-ALFA-002",
        terceirizada_id="ter_alfa_1",
        exigencias_ids=["tdoc_aso"],
        offset_inicio_dias=-60,
        offset_fim_dias=300,
        vigente=True,
    )
    ctr_alfa_3 = ContratoSeed(
        id="ctr_alfa_3",
        identificador="CTR-ALFA-003",
        terceirizada_id="ter_alfa_2",
        exigencias_ids=["tdoc_aso"],
        offset_inicio_dias=-30,
        offset_fim_dias=330,
        vigente=True,
    )
    ctr_alfa_4 = ContratoSeed(
        id="ctr_alfa_4",
        identificador="CTR-ALFA-004",
        terceirizada_id="ter_alfa_1",
        exigencias_ids=["tdoc_aso"],
        offset_inicio_dias=-370,
        offset_fim_dias=-10,
        vigente=False,  # Encerrado
    )

    usuarios_alfa = [
        UsuarioSeed(
            uid="uid_gestor_alfa",
            email="gestor.alfa@demo.habilita.test",
            nome="Gestor SST Alfa",
            papel="gestor",
            tenant_id="tnt_alfa",
        ),
        UsuarioSeed(
            uid="uid_porteiro_alfa",
            email="porteiro.alfa@demo.habilita.test",
            nome="Porteiro Principal Alfa",
            papel="porteiro",
            tenant_id="tnt_alfa",
        ),
        UsuarioSeed(
            uid="uid_terc_alfa_1",
            email="terceirizada1.alfa@demo.habilita.test",
            nome="Responsavel Terceirizada 1 Alfa",
            papel="terceirizada",
            tenant_id="tnt_alfa",
            terceirizada_id="ter_alfa_1",
        ),
        UsuarioSeed(
            uid="uid_terc_alfa_2",
            email="terceirizada2.alfa@demo.habilita.test",
            nome="Responsavel Terceirizada 2 Alfa",
            papel="terceirizada",
            tenant_id="tnt_alfa",
            terceirizada_id="ter_alfa_2",
        ),
    ]

    # Trabalhadores Alfa
    trabalhadores_alfa = [
        # trb_alfa_1: ASO D+200, NR-35 D+500 -> verde nos dois contratos (reuso do ASO)
        TrabalhadorSeed(
            id="trb_alfa_1",
            terceirizada_id="ter_alfa_1",
            nome="Carlos Silva Santos",
            cpf_base="101000001",
            ativo=True,
            contratos_alocados=["ctr_alfa_1", "ctr_alfa_2"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_1_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_1_nr35",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=500,
                    offset_data_emissao_dias=-230,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_2: ASO D+20 (a vencer), NR-35 D+400 -> amarelo
        TrabalhadorSeed(
            id="trb_alfa_2",
            terceirizada_id="ter_alfa_1",
            nome="Marcos Oliveira Lima",
            cpf_base="101000002",
            ativo=True,
            contratos_alocados=["ctr_alfa_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_2_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=20,
                    offset_data_emissao_dias=-345,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_2_nr35",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=400,
                    offset_data_emissao_dias=-330,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_3: ASO D-1 (vencido), NR-35 D+400 -> vermelho
        TrabalhadorSeed(
            id="trb_alfa_3",
            terceirizada_id="ter_alfa_1",
            nome="Jose Roberto Souza",
            cpf_base="101000003",
            ativo=True,
            contratos_alocados=["ctr_alfa_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_3_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=-1,
                    offset_data_emissao_dias=-366,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_3_nr35",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=400,
                    offset_data_emissao_dias=-330,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_4: ASO D+200, NR-35 ausente -> vermelho
        TrabalhadorSeed(
            id="trb_alfa_4",
            terceirizada_id="ter_alfa_1",
            nome="Antonio Ferreira Costa",
            cpf_base="101000004",
            ativo=True,
            contratos_alocados=["ctr_alfa_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_4_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_5: ASO D+200, NR-35 apenas pendente -> vermelho
        TrabalhadorSeed(
            id="trb_alfa_5",
            terceirizada_id="ter_alfa_1",
            nome="Fernando Alves Rocha",
            cpf_base="101000005",
            ativo=True,
            contratos_alocados=["ctr_alfa_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_5_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_5_nr35_pendente",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=300,
                    offset_data_emissao_dias=-65,
                    status_revisao="PENDENTE",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid=None,
                ),
            ],
        ),
        # trb_alfa_6: ASO D+200, NR-35 rejeitada E outra NR-35 ok D+365 -> verde (cenário Q1)
        # Nota sobre a questão Q1: Um documento rejeitado não anula outro aprovado e válido.
        TrabalhadorSeed(
            id="trb_alfa_6",
            terceirizada_id="ter_alfa_1",
            nome="Rafael Mendes Ribeiro",
            cpf_base="101000006",
            ativo=True,
            contratos_alocados=["ctr_alfa_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_6_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_6_nr35_rejeitado",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=300,
                    offset_data_emissao_dias=-65,
                    status_revisao="REJEITADO",
                    motivo_rejeicao="Documento ilegivel: carimbo cortado na digitalizacao",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
                DocumentoSeed(
                    id="doc_alfa_6_nr35_aprovado",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=365,
                    offset_data_emissao_dias=-20,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_7: ASO D+200, só em ctr_alfa_4 (encerrado) -> verde na alocação,
        # mas bloqueia na portaria (RN-10)
        TrabalhadorSeed(
            id="trb_alfa_7",
            terceirizada_id="ter_alfa_1",
            nome="Lucas Pereira Castro",
            cpf_base="101000007",
            ativo=True,
            contratos_alocados=["ctr_alfa_4"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_7_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_8: ASO D+200, ativo=False -> verde na alocação,
        # mas bloqueia na portaria (RN-10)
        TrabalhadorSeed(
            id="trb_alfa_8",
            terceirizada_id="ter_alfa_1",
            nome="Bruno Cardoso Dias",
            cpf_base="101000008",
            ativo=False,
            contratos_alocados=["ctr_alfa_2"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_8_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_1",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
        # trb_alfa_y1: terceirizada 2, ASO D+200 em ctr_alfa_3 -> verde
        TrabalhadorSeed(
            id="trb_alfa_y1",
            terceirizada_id="ter_alfa_2",
            nome="Rodrigo Martins Teixeira",
            cpf_base="101000009",
            ativo=True,
            contratos_alocados=["ctr_alfa_3"],
            documentos=[
                DocumentoSeed(
                    id="doc_alfa_y1_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_alfa_2",
                    revisado_por_uid="uid_gestor_alfa",
                ),
            ],
        ),
    ]

    tenant_alfa = TenantSeed(
        id="tnt_alfa",
        nome="Empresa Contratante Alfa S.A.",
        tipos_documento=[tdoc_aso, tdoc_nr35],
        terceirizadas=[ter_alfa_1, ter_alfa_2],
        contratos=[ctr_alfa_1, ctr_alfa_2, ctr_alfa_3, ctr_alfa_4],
        trabalhadores=trabalhadores_alfa,
        usuarios=usuarios_alfa,
    )

    # -------------------------------------------------------------------------
    # TENANT BETA (Espelho enxuto para testes de isolamento de tenant)
    # -------------------------------------------------------------------------
    ter_beta_1 = TerceirizadaSeed(
        id="ter_beta_1",
        razao_social="Beta Engenharia e Infraestrutura Ltda",
        cnpj_base="333333330001",
    )
    ter_beta_2 = TerceirizadaSeed(
        id="ter_beta_2",
        razao_social="Beta Logistica e Transportes Ltda",
        cnpj_base="444444440001",
    )

    ctr_beta_1 = ContratoSeed(
        id="ctr_beta_1",
        identificador="CTR-BETA-001",
        terceirizada_id="ter_beta_1",
        exigencias_ids=["tdoc_aso", "tdoc_nr35"],
        offset_inicio_dias=-60,
        offset_fim_dias=300,
        vigente=True,
    )
    ctr_beta_2 = ContratoSeed(
        id="ctr_beta_2",
        identificador="CTR-BETA-002",
        terceirizada_id="ter_beta_2",
        exigencias_ids=["tdoc_aso"],
        offset_inicio_dias=-30,
        offset_fim_dias=330,
        vigente=True,
    )

    usuarios_beta = [
        UsuarioSeed(
            uid="uid_gestor_beta",
            email="gestor.beta@demo.habilita.test",
            nome="Gestor SST Beta",
            papel="gestor",
            tenant_id="tnt_beta",
        ),
        UsuarioSeed(
            uid="uid_porteiro_beta",
            email="porteiro.beta@demo.habilita.test",
            nome="Porteiro Principal Beta",
            papel="porteiro",
            tenant_id="tnt_beta",
        ),
        UsuarioSeed(
            uid="uid_terc_beta_1",
            email="terceirizada1.beta@demo.habilita.test",
            nome="Responsavel Terceirizada 1 Beta",
            papel="terceirizada",
            tenant_id="tnt_beta",
            terceirizada_id="ter_beta_1",
        ),
        UsuarioSeed(
            uid="uid_terc_beta_2",
            email="terceirizada2.beta@demo.habilita.test",
            nome="Responsavel Terceirizada 2 Beta",
            papel="terceirizada",
            tenant_id="tnt_beta",
            terceirizada_id="ter_beta_2",
        ),
    ]

    # CPFs do Tenant Beta iniciados em "202..." para garantir que nenhum CPF se repete
    trabalhadores_beta = [
        # trb_beta_1: verde
        TrabalhadorSeed(
            id="trb_beta_1",
            terceirizada_id="ter_beta_1",
            nome="Alexandre Pires Barbosa",
            cpf_base="202000001",
            ativo=True,
            contratos_alocados=["ctr_beta_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_beta_1_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_beta_1",
                    revisado_por_uid="uid_gestor_beta",
                ),
                DocumentoSeed(
                    id="doc_beta_1_nr35",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=400,
                    offset_data_emissao_dias=-330,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_beta_1",
                    revisado_por_uid="uid_gestor_beta",
                ),
            ],
        ),
        # trb_beta_2: vermelho por ASO vencido
        TrabalhadorSeed(
            id="trb_beta_2",
            terceirizada_id="ter_beta_1",
            nome="Daniel Goncalves Ramos",
            cpf_base="202000002",
            ativo=True,
            contratos_alocados=["ctr_beta_1"],
            documentos=[
                DocumentoSeed(
                    id="doc_beta_2_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=-5,
                    offset_data_emissao_dias=-370,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_beta_1",
                    revisado_por_uid="uid_gestor_beta",
                ),
                DocumentoSeed(
                    id="doc_beta_2_nr35",
                    tipo_documento_id="tdoc_nr35",
                    offset_valido_ate_dias=400,
                    offset_data_emissao_dias=-330,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_beta_1",
                    revisado_por_uid="uid_gestor_beta",
                ),
            ],
        ),
        # trb_beta_y1: terceirizada 2, verde
        TrabalhadorSeed(
            id="trb_beta_y1",
            terceirizada_id="ter_beta_2",
            nome="Guilherme Moreira Neves",
            cpf_base="202000003",
            ativo=True,
            contratos_alocados=["ctr_beta_2"],
            documentos=[
                DocumentoSeed(
                    id="doc_beta_y1_aso",
                    tipo_documento_id="tdoc_aso",
                    offset_valido_ate_dias=200,
                    offset_data_emissao_dias=-165,
                    status_revisao="APROVADO",
                    enviado_por_uid="uid_terc_beta_2",
                    revisado_por_uid="uid_gestor_beta",
                ),
            ],
        ),
    ]

    tenant_beta = TenantSeed(
        id="tnt_beta",
        nome="Empresa Contratante Beta S.A.",
        tipos_documento=[tdoc_aso, tdoc_nr35],
        terceirizadas=[ter_beta_1, ter_beta_2],
        contratos=[ctr_beta_1, ctr_beta_2],
        trabalhadores=trabalhadores_beta,
        usuarios=usuarios_beta,
    )

    return [tenant_alfa, tenant_beta]


def preparar_documento_firestore(
    tenant_id: str,
    trabalhador_id: str,
    doc_seed: DocumentoSeed,
    data_referencia: date,
    tipo_nome: str,
    pdf_bytes: bytes,
    pdf_sha256: str,
) -> dict[str, Any]:
    """Monta o documento conforme modelo de dados para persistência no Firestore."""
    valido_ate = data_referencia + timedelta(days=doc_seed.offset_valido_ate_dias)
    data_emissao_str: str | None = None
    if doc_seed.offset_data_emissao_dias is not None:
        data_emissao = data_referencia + timedelta(days=doc_seed.offset_data_emissao_dias)
        data_emissao_str = data_emissao.isoformat()

    file_uuid = derivar_uuid_arquivo(tenant_id, trabalhador_id, doc_seed.id)
    storage_path = (
        f"tenants/{tenant_id}/trabalhadores/{trabalhador_id}/"
        f"documentos/{doc_seed.id}/{file_uuid}.pdf"
    )

    situacao_validade: str | None = None
    if doc_seed.status_revisao == "APROVADO":
        situacao_validade = calcular_situacao_validade(valido_ate, data_referencia)

    enviado_em = f"{data_referencia.isoformat()}T10:00:00Z"
    revisado_em: str | None = None
    if doc_seed.revisado_por_uid:
        revisado_em = f"{data_referencia.isoformat()}T11:00:00Z"

    return {
        "id": doc_seed.id,
        "trabalhadorId": trabalhador_id,
        "tipoDocumentoId": doc_seed.tipo_documento_id,
        "dataEmissao": data_emissao_str,
        "validoAte": valido_ate.isoformat(),
        "statusRevisao": doc_seed.status_revisao,
        "situacaoValidade": situacao_validade,
        "motivoRejeicao": doc_seed.motivo_rejeicao,
        "arquivo": {
            "caminho": storage_path,
            "contentType": "application/pdf",
            "tamanhoBytes": len(pdf_bytes),
            "sha256": pdf_sha256,
        },
        "enviadoPor": doc_seed.enviado_por_uid,
        "enviadoEm": enviado_em,
        "revisadoPor": doc_seed.revisado_por_uid,
        "revisadoEm": revisado_em,
    }
