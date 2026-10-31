"""Integração com os emuladores Firebase (Auth e Firestore) e Supabase Storage."""

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import firebase_admin
import google.auth.credentials
from firebase_admin import auth, credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from habilita_seed.config import SeedConfig
from habilita_seed.cpf import calcular_cpf_hash
from habilita_seed.dados import (
    TenantSeed,
    preparar_documento_firestore,
)
from habilita_seed.pdf import calcular_sha256, derivar_uuid_arquivo, gerar_pdf_ficticio

logger = logging.getLogger("habilita_seed")


class EmulatorCredentials(credentials.Base):  # type: ignore[misc]
    """Credencial anônima segura para conexão exclusiva com os emuladores locais."""

    def get_credential(self) -> google.auth.credentials.Credentials:
        return google.auth.credentials.AnonymousCredentials()  # type: ignore[no-untyped-call]


def obter_firebase_app(config: SeedConfig) -> firebase_admin.App:
    """Inicializa ou recupera a instância padrão do Firebase Admin SDK."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(
            credential=EmulatorCredentials(),
            options={
                "projectId": config.project_id,
            },
        )


def resetar_emuladores(config: SeedConfig) -> None:
    """Limpa determinística e completamente os dados de Auth, Firestore e Storage."""
    logger.info("Iniciando reset dos serviços locais...")

    # 1. Reset do Auth Emulator via API REST oficial do emulador
    auth_url = (
        f"http://{config.auth_emulator_host}/emulator/v1/projects/{config.project_id}/accounts"
    )
    try:
        req = urllib.request.Request(auth_url, method="DELETE")
        # Requisição local aos emuladores; esquema http validado acima
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            if resp.status not in (200, 204):
                logger.warning("Resposta inesperada ao resetar Auth: HTTP %s", resp.status)
        logger.info("Emulador de Auth limpo com sucesso.")
    except Exception as exc:
        logger.warning("Falha ao resetar emulador de Auth via REST: %s", exc)

    # 2. Reset do Firestore Emulator via API REST oficial do emulador
    firestore_url = (
        f"http://{config.firestore_emulator_host}/emulator/v1/projects/"
        f"{config.project_id}/databases/(default)/documents"
    )
    try:
        req = urllib.request.Request(firestore_url, method="DELETE")
        # Requisição local aos emuladores; esquema http validado acima
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            if resp.status not in (200, 204):
                logger.warning("Resposta inesperada ao resetar Firestore: HTTP %s", resp.status)
        logger.info("Emulador de Firestore limpo com sucesso.")
    except Exception as exc:
        logger.warning("Falha ao resetar emulador de Firestore via REST: %s", exc)

    # 3. Reset do Supabase Storage via API REST (esvaziar bucket)
    try:
        url = f"{config.storage_url.rstrip('/')}/bucket/{config.storage_bucket}/empty"
        req = urllib.request.Request(  # noqa: S310
            url,
            headers={"Authorization": f"Bearer {config.storage_service_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            if resp.status in (200, 201):
                logger.info(
                    "Bucket de Storage ('%s') esvaziado com sucesso.", config.storage_bucket
                )
            else:
                logger.warning("Resposta inesperada ao esvaziar bucket: HTTP %s", resp.status)
    except Exception as exc:
        logger.warning("Falha ao esvaziar bucket do Supabase Storage via REST: %s", exc)


def popular_usuarios(config: SeedConfig, tenants: list[TenantSeed]) -> int:
    """Cria e configura os usuários de demonstração com senha fixa e custom claims."""
    total = 0
    obter_firebase_app(config)

    for tenant in tenants:
        for usuario in tenant.usuarios:
            try:
                auth.create_user(
                    uid=usuario.uid,
                    email=usuario.email,
                    display_name=usuario.nome,
                    password=config.senha_padrao,
                    email_verified=True,
                )
            except auth.UidAlreadyExistsError:
                auth.update_user(
                    usuario.uid,
                    email=usuario.email,
                    display_name=usuario.nome,
                    password=config.senha_padrao,
                    email_verified=True,
                )

            # Atribuição estrita das custom claims (ADR 0002)
            auth.set_custom_user_claims(usuario.uid, usuario.custom_claims)
            total += 1

    logger.info("Populados %d usuários no emulador de Auth com custom claims.", total)
    return total


def enviar_arquivo_supabase(
    config: SeedConfig,
    caminho: str,
    conteudo: bytes,
    content_type: str = "application/pdf",
) -> None:
    """Envia um arquivo para o Supabase Storage via API REST usando a chave de serviço.

    Utiliza o cabeçalho 'x-upsert: true' para garantir idempotência estrita:
    se o arquivo já existir no bucket, ele é sobrescrito sem falhar.
    """
    url = f"{config.storage_url.rstrip('/')}/object/{config.storage_bucket}/{caminho}"
    req = urllib.request.Request(  # noqa: S310
        url,
        data=conteudo,
        headers={
            "Authorization": f"Bearer {config.storage_service_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        if resp.status not in (200, 201):
            raise RuntimeError(
                f"Falha ao enviar arquivo para o Supabase Storage (HTTP {resp.status})"
            )


def baixar_objeto_supabase(config: SeedConfig, caminho: str) -> tuple[bytes, str]:
    """Baixa o conteúdo e o Content-Type do objeto do Supabase Storage via REST."""
    url = f"{config.storage_url.rstrip('/')}/object/authenticated/{config.storage_bucket}/{caminho}"
    req = urllib.request.Request(  # noqa: S310
        url,
        headers={"Authorization": f"Bearer {config.storage_service_key}"},
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        content_type = resp.headers.get("Content-Type", "")
        return resp.read(), content_type


def popular_firestore_e_storage(
    config: SeedConfig,
    tenants: list[TenantSeed],
    data_referencia: date,
) -> dict[str, int]:
    """Grava as coleções no Firestore e envia os arquivos binários ao Storage."""
    app = obter_firebase_app(config)
    db: FirestoreClient = firestore.client(app=app)

    contagens: dict[str, int] = {
        "tenants": 0,
        "tipos_documento": 0,
        "terceirizadas": 0,
        "contratos": 0,
        "trabalhadores": 0,
        "documentos": 0,
        "alocacoes": 0,
        "indices_cpf": 0,
        "storage_objetos": 0,
    }

    for tenant in tenants:
        # Documento raiz do tenant
        tenant_ref = db.collection("tenants").document(tenant.id)
        tenant_ref.set(
            {
                "id": tenant.id,
                "nome": tenant.nome,
                "criadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
            }
        )
        contagens["tenants"] += 1

        tipos_map = {t.id: t for t in tenant.tipos_documento}

        # 1. Tipos de documento
        for tipo in tenant.tipos_documento:
            tipo_ref = tenant_ref.collection("tiposDocumento").document(tipo.id)
            tipo_ref.set(
                {
                    "id": tipo.id,
                    "nome": tipo.nome,
                    "validadeMeses": tipo.validade_meses,
                    "ativo": tipo.ativo,
                    "criadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
                }
            )
            contagens["tipos_documento"] += 1

        # 2. Terceirizadas
        for ter in tenant.terceirizadas:
            ter_ref = tenant_ref.collection("terceirizadas").document(ter.id)
            ter_ref.set(
                {
                    "id": ter.id,
                    "razaoSocial": ter.razao_social,
                    "cnpj": ter.cnpj,
                    "ativa": ter.ativa,
                    "criadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
                }
            )
            contagens["terceirizadas"] += 1

        # 3. Contratos
        contratos_map = {c.id: c for c in tenant.contratos}
        for ctr in tenant.contratos:
            dt_inicio = data_referencia + timedelta(days=ctr.offset_inicio_dias)
            dt_fim = data_referencia + timedelta(days=ctr.offset_fim_dias)
            exigencias_docs = [
                {
                    "id": tipos_map[eid].id,
                    "nome": tipos_map[eid].nome,
                    "validadeMeses": tipos_map[eid].validade_meses,
                }
                for eid in ctr.exigencias_ids
            ]
            ctr_ref = tenant_ref.collection("contratos").document(ctr.id)
            ctr_ref.set(
                {
                    "id": ctr.id,
                    "identificador": ctr.identificador,
                    "terceirizadaId": ctr.terceirizada_id,
                    "dataInicio": dt_inicio.isoformat(),
                    "dataFim": dt_fim.isoformat(),
                    "vigente": ctr.vigente,
                    "versaoMatriz": ctr.versao_matriz,
                    "exigencias": exigencias_docs,
                    "criadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
                }
            )
            contagens["contratos"] += 1

        # 4. Trabalhadores, Documentos, Upload no Storage e Índice CPF
        for trb in tenant.trabalhadores:
            trb_ref = tenant_ref.collection("trabalhadores").document(trb.id)
            trb_ref.set(
                {
                    "id": trb.id,
                    "terceirizadaId": trb.terceirizada_id,
                    "nome": trb.nome,
                    "cpfMascarado": trb.cpf_mascarado,
                    "ativo": trb.ativo,
                    "criadoEm": f"{data_referencia.isoformat()}T00:00:00Z",
                }
            )
            contagens["trabalhadores"] += 1

            # Índice de CPF (ADR 0008)
            cpf_hash = calcular_cpf_hash(config.cpf_hmac_key, trb.cpf)
            indice_ref = tenant_ref.collection("indiceCpf").document(cpf_hash)
            indice_ref.set({"trabalhadorId": trb.id})
            contagens["indices_cpf"] += 1

            # Documentos do trabalhador (3 documentos por trabalhador: ASO, NR-35, NR-10)
            for doc in trb.documentos:
                tipo_obj = tipos_map[doc.tipo_documento_id]
                dt_valido = data_referencia + timedelta(days=doc.offset_valido_ate_dias)
                pdf_bytes = gerar_pdf_ficticio(
                    documento_id=doc.id,
                    trabalhador_id=trb.id,
                    tipo_nome=tipo_obj.nome,
                    valido_ate=dt_valido.isoformat(),
                    detalhes=doc.motivo_rejeicao or doc.status_revisao,
                )
                pdf_sha256 = calcular_sha256(pdf_bytes)

                # Upload binário para o Supabase Storage
                file_uuid = derivar_uuid_arquivo(tenant.id, trb.id, doc.id)
                storage_path = (
                    f"tenants/{tenant.id}/trabalhadores/{trb.id}/"
                    f"documentos/{doc.id}/{file_uuid}.pdf"
                )
                enviar_arquivo_supabase(
                    config=config,
                    caminho=storage_path,
                    conteudo=pdf_bytes,
                    content_type="application/pdf",
                )
                contagens["storage_objetos"] += 1

                # Gravação dos metadados no Firestore
                doc_payload = preparar_documento_firestore(
                    tenant_id=tenant.id,
                    trabalhador_id=trb.id,
                    doc_seed=doc,
                    data_referencia=data_referencia,
                    tipo_nome=tipo_obj.nome,
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=pdf_sha256,
                )
                doc_ref = trb_ref.collection("documentos").document(doc.id)
                doc_ref.set(doc_payload)
                contagens["documentos"] += 1

            # 5. Alocações do trabalhador nos contratos
            from habilita_seed.dados import calcular_alocacao

            for ctr_id in trb.contratos_alocados:
                ctr_seed = contratos_map[ctr_id]
                alocacao_payload = calcular_alocacao(
                    contrato=ctr_seed,
                    trabalhador=trb,
                    data_referencia=data_referencia,
                    tipos_por_id=tipos_map,
                )
                aloc_ref = (
                    tenant_ref.collection("contratos")
                    .document(ctr_id)
                    .collection("alocacoes")
                    .document(trb.id)
                )
                aloc_ref.set(alocacao_payload)
                contagens["alocacoes"] += 1

    return contagens


def calcular_checksum_firestore(config: SeedConfig) -> str:
    """Calcula um checksum SHA-256 canônico e estritamente normalizado do banco."""
    app = obter_firebase_app(config)
    db: FirestoreClient = firestore.client(app=app)

    items: list[tuple[str, str]] = []

    tenants_docs = sorted(db.collection("tenants").stream(), key=lambda d: d.id)
    for t_doc in tenants_docs:
        t_id = t_doc.id
        t_path = f"tenants/{t_id}"
        items.append(
            (
                t_path,
                json.dumps(t_doc.to_dict(), sort_keys=True, separators=(",", ":")),
            )
        )

        subcolecoes = [
            ("tiposDocumento", []),
            ("terceirizadas", []),
            ("contratos", ["alocacoes"]),
            ("trabalhadores", ["documentos"]),
            ("indiceCpf", []),
        ]

        for sub_nome, nested_list in subcolecoes:
            sub_ref = t_doc.reference.collection(sub_nome)
            docs = sorted(sub_ref.stream(), key=lambda d: d.id)
            for d in docs:
                d_path = f"{t_path}/{sub_nome}/{d.id}"
                items.append(
                    (
                        d_path,
                        json.dumps(d.to_dict(), sort_keys=True, separators=(",", ":")),
                    )
                )

                for nested_nome in nested_list:
                    nested_ref = d.reference.collection(nested_nome)
                    n_docs = sorted(nested_ref.stream(), key=lambda nd: nd.id)
                    for nd in n_docs:
                        nd_path = f"{d_path}/{nested_nome}/{nd.id}"
                        items.append(
                            (
                                nd_path,
                                json.dumps(
                                    nd.to_dict(),
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            )
                        )

    # Ordenação canônica por caminho do documento
    items.sort(key=lambda item: item[0])

    hasher = hashlib.sha256()
    for path, data_json in items:
        hasher.update(path.encode("utf-8"))
        hasher.update(b"=")
        hasher.update(data_json.encode("utf-8"))
        hasher.update(b"\n")

    return hasher.hexdigest()


def verificar_integridade(config: SeedConfig, data_referencia: date) -> tuple[bool, list[str], str]:
    """Verifica contagens, integridade de isolamento, regras e calcula o checksum."""
    erros: list[str] = []
    app = obter_firebase_app(config)
    db: FirestoreClient = firestore.client(app=app)

    # 1. Checagem de Usuários e Claims no Auth
    usuarios_esperados = {
        "uid_gestor_alfa": {"tenantId": "tnt_alfa", "papel": "gestor"},
        "uid_porteiro_alfa": {"tenantId": "tnt_alfa", "papel": "porteiro"},
        "uid_terc_alfa_1": {
            "tenantId": "tnt_alfa",
            "papel": "terceirizada",
            "terceirizadaId": "ter_alfa_1",
        },
        "uid_terc_alfa_2": {
            "tenantId": "tnt_alfa",
            "papel": "terceirizada",
            "terceirizadaId": "ter_alfa_2",
        },
        "uid_gestor_beta": {"tenantId": "tnt_beta", "papel": "gestor"},
        "uid_porteiro_beta": {"tenantId": "tnt_beta", "papel": "porteiro"},
        "uid_terc_beta_1": {
            "tenantId": "tnt_beta",
            "papel": "terceirizada",
            "terceirizadaId": "ter_beta_1",
        },
        "uid_terc_beta_2": {
            "tenantId": "tnt_beta",
            "papel": "terceirizada",
            "terceirizadaId": "ter_beta_2",
        },
    }

    for uid, claims_esperadas in usuarios_esperados.items():
        try:
            user_record = auth.get_user(uid)
            claims = user_record.custom_claims or {}
            for k, v in claims_esperadas.items():
                if claims.get(k) != v:
                    erros.append(f"Usuário {uid}: claim '{k}' = '{claims.get(k)}', esperado '{v}'.")
            if claims.get("papel") != "terceirizada" and "terceirizadaId" in claims:
                erros.append(f"Usuário {uid}: não é terceirizada mas possui 'terceirizadaId'.")
        except Exception as exc:
            erros.append(f"Falha ao ler usuário Auth {uid}: {exc}")

    # 2. Checagem de documentos no Firestore e arquivos no Supabase Storage
    tenants = ["tnt_alfa", "tnt_beta"]

    cpfs_alfa: set[str] = set()
    cpfs_beta: set[str] = set()

    for t_id in tenants:
        t_ref = db.collection("tenants").document(t_id)

        # Checar trabalhadores e CPFs
        trabalhadores = list(t_ref.collection("trabalhadores").stream())
        for trb in trabalhadores:
            docs = list(trb.reference.collection("documentos").stream())
            for d in docs:
                doc_data = d.to_dict()
                arq = doc_data.get("arquivo", {})
                caminho = arq.get("caminho", "")

                # Isolamento de caminho
                if not caminho.startswith(f"tenants/{t_id}/"):
                    erros.append(
                        f"Vazamento de isolamento no caminho do documento {d.id}: '{caminho}'."
                    )

                # Conferir integridade no Supabase Storage
                try:
                    conteudo, ctype = baixar_objeto_supabase(config, caminho)
                    if "application/pdf" not in ctype:
                        erros.append(
                            f"Arquivo '{caminho}' possui contentType '{ctype}', "
                            "esperado 'application/pdf'."
                        )
                    sha_real = hashlib.sha256(conteudo).hexdigest()
                    if sha_real != arq.get("sha256"):
                        erros.append(
                            f"Hash divergente no documento {d.id}: real '{sha_real}' "
                            f"!= armazenado '{arq.get('sha256')}'."
                        )
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        erros.append(f"Arquivo não encontrado no Storage: '{caminho}'.")
                    else:
                        erros.append(f"Erro ao baixar blob '{caminho}': HTTP {exc.code}")
                except Exception as exc:
                    erros.append(f"Falha ao baixar blob '{caminho}': {exc}")

        # Checar alocações e semáforo
        contratos = list(t_ref.collection("contratos").stream())
        for ctr in contratos:
            alocs = list(ctr.reference.collection("alocacoes").stream())
            for aloc in alocs:
                aloc_data = aloc.to_dict()
                semaforo = aloc_data.get("semaforo")
                if semaforo not in ("VERDE", "AMARELO", "VERMELHO"):
                    erros.append(
                        f"Semáforo inválido na alocação {aloc.id} do contrato {ctr.id}: "
                        f"'{semaforo}'."
                    )

        # Checar CPFs no índice
        indices = list(t_ref.collection("indiceCpf").stream())
        for ind in indices:
            if t_id == "tnt_alfa":
                cpfs_alfa.add(ind.id)
            elif t_id == "tnt_beta":
                cpfs_beta.add(ind.id)

    # 3. Isolamento estrito entre tenants
    intersecao_cpfs = cpfs_alfa.intersection(cpfs_beta)
    if intersecao_cpfs:
        erros.append(f"Vazamento de isolamento de CPFs entre Alfa e Beta: {intersecao_cpfs}.")

    # 4. Cálculo do Checksum Canônico do Firestore
    checksum = calcular_checksum_firestore(config)

    return (len(erros) == 0, erros, checksum)
