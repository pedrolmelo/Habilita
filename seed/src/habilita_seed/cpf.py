"""Geração e manipulação de CPF e CNPJ fictícios com dígitos válidos, máscara e HMAC."""

import hashlib
import hmac
import re

PADRAO_APENAS_DIGITOS = re.compile(r"\D")


def normalizar_digitos(documento: str) -> str:
    """Remove pontuações e caracteres não numéricos."""
    return PADRAO_APENAS_DIGITOS.sub("", documento)


def calcular_digitos_cpf(nove_digitos: str) -> str:
    """Calcula os dois dígitos verificadores de um CPF a partir de seus 9 primeiros dígitos.

    Retorna o CPF normalizado completo com 11 dígitos válidos.
    """
    digitos = [int(c) for c in nove_digitos[:9]]
    if len(digitos) < 9:
        raise ValueError("O CPF base deve possuir ao menos 9 dígitos.")

    # 1º dígito verificador
    soma1 = sum(digitos[i] * (10 - i) for i in range(9))
    resto1 = (soma1 * 10) % 11
    d1 = 0 if resto1 == 10 else resto1
    digitos.append(d1)

    # 2º dígito verificador
    soma2 = sum(digitos[i] * (11 - i) for i in range(10))
    resto2 = (soma2 * 10) % 11
    d2 = 0 if resto2 == 10 else resto2

    return "".join(str(d) for d in digitos[:9]) + f"{d1}{d2}"


def calcular_digitos_cnpj(doze_digitos: str) -> str:
    """Calcula os dois dígitos verificadores de um CNPJ a partir de seus 12 primeiros dígitos.

    Retorna o CNPJ normalizado completo com 14 dígitos válidos.
    """
    digitos = [int(c) for c in doze_digitos[:12]]
    if len(digitos) < 12:
        raise ValueError("O CNPJ base deve possuir ao menos 12 dígitos.")

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(digitos[i] * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    d1 = 0 if resto1 < 2 else 11 - resto1
    digitos.append(d1)

    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(digitos[i] * pesos2[i] for i in range(13))
    resto2 = soma2 % 11
    d2 = 0 if resto2 < 2 else 11 - resto2

    return "".join(str(d) for d in digitos[:12]) + f"{d1}{d2}"


def mascarar_cpf(cpf: str) -> str:
    """Gera o formato mascarado para exibição: ***.456.789-** conforme ADR 0008."""
    digitos = normalizar_digitos(cpf)
    if len(digitos) != 11:
        raise ValueError(f"CPF inválido para máscara: deve conter 11 dígitos, obtido '{cpf}'.")
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**"


def calcular_cpf_hash(chave_hmac: str, cpf: str) -> str:
    """Gera o HMAC-SHA256 em hexadecimal a partir do CPF normalizado conforme ADR 0008."""
    cpf_limpo = normalizar_digitos(cpf)
    return hmac.new(
        chave_hmac.encode("utf-8"), cpf_limpo.encode("utf-8"), hashlib.sha256
    ).hexdigest()
