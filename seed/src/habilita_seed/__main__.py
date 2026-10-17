"""Ponto de entrada (CLI) do gerador determinístico de seed do Habilita."""

import argparse
import logging
import sys
from datetime import date

from habilita_seed.config import TravaEmuladorError, validar_trava_emulador
from habilita_seed.dados import construir_cenarios_seed
from habilita_seed.emuladores import (
    popular_firestore_e_storage,
    popular_usuarios,
    resetar_emuladores,
    verificar_integridade,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("habilita_seed")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Popula os emuladores do Firebase com dados determinísticos de demonstração."
    )
    parser.add_argument(
        "--reset",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Limpa os emuladores antes de popular os dados (padrão: ativo).",
    )
    parser.add_argument(
        "--hoje",
        type=str,
        default="2026-10-20",
        help="Data de referência YYYY-MM-DD para vigências e validades (padrão: 2026-10-20).",
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        default=False,
        help="Apenas valida a integridade e imprime o checksum, sem escrever.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        data_referencia = date.fromisoformat(args.hoje)
    except ValueError:
        logger.error(
            "Data de referência inválida: '%s'. Utilize o formato YYYY-MM-DD.",
            args.hoje,
        )
        return 1

    logger.info(
        "=== HABILITA SEED (Data de referência: %s) ===",
        data_referencia.isoformat(),
    )

    # 1. Execução obrigatória da Trava de Segurança do Emulador
    try:
        config = validar_trava_emulador()
    except TravaEmuladorError as err:
        logger.error("%s", err)
        return 1

    logger.info("Trava de segurança validada: executando estritamente contra emuladores locais.")
    logger.info("Projeto: %s", config.project_id)
    logger.info("Auth Emulator: %s", config.auth_emulator_host)
    logger.info("Firestore Emulator: %s", config.firestore_emulator_host)
    logger.info(
        "Storage Emulator: %s (bucket: %s)",
        config.storage_emulator_host,
        config.storage_bucket,
    )

    # Modo somente verificação
    if args.verificar:
        logger.info("Modo --verificar acionado: nenhuma escrita será realizada.")
        ok, erros, checksum = verificar_integridade(config, data_referencia)
        if not ok:
            logger.error("Erros de integridade detectados:")
            for erro in erros:
                logger.error("  - %s", erro)
            return 1
        logger.info("Integridade e isolamento validados com sucesso!")
        logger.info("CHECKSUM FIRESTORE: %s", checksum)
        return 0

    # 2. Reset (se solicitado)
    if args.reset:
        resetar_emuladores(config)

    # 3. Construção e gravação dos cenários
    tenants = construir_cenarios_seed()
    total_usuarios = popular_usuarios(config, tenants)
    contagens = popular_firestore_e_storage(config, tenants, data_referencia)

    # 4. Verificação de integridade e checksum
    ok, erros, checksum = verificar_integridade(config, data_referencia)
    if not ok:
        logger.error("Erros de validação pós-gravação:")
        for erro in erros:
            logger.error("  - %s", erro)
        return 1

    logger.info("=== RESUMO DO SEED EXECUTADO COM SUCESSO ===")
    logger.info("  Usuários Auth criados:       %d", total_usuarios)
    logger.info("  Tenants criados:             %d", contagens["tenants"])
    logger.info("  Tipos de documento criados:  %d", contagens["tipos_documento"])
    logger.info("  Terceirizadas cadastradas:   %d", contagens["terceirizadas"])
    logger.info("  Contratos cadastrados:       %d", contagens["contratos"])
    logger.info("  Trabalhadores cadastrados:   %d", contagens["trabalhadores"])
    logger.info("  Documentos registrados:      %d", contagens["documentos"])
    logger.info("  Alocações (semáforo):        %d", contagens["alocacoes"])
    logger.info("  Índices de CPF criados:      %d", contagens["indices_cpf"])
    logger.info("  Objetos enviados ao Storage: %d", contagens["storage_objetos"])
    logger.info("  CHECKSUM FIRESTORE:          %s", checksum)
    return 0


if __name__ == "__main__":
    sys.exit(main())
