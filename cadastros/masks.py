import re

PHONE_DIGITS = 11      # celular: DDD + 9 dígitos
LANDLINE_DIGITS = 10   # fixo: DDD + 8 dígitos
CPF_DIGITS = 11
CNPJ_DIGITS = 14

PHONE_FORMAT = "(NN) NNNNN-NNNN"
LANDLINE_FORMAT = "(NN) NNNN-NNNN"
CPF_FORMAT = "000.000.000-00"
CNPJ_FORMAT = "00.000.000/0000-00"


def only_digits(value):
    return re.sub(r"\D", "", str(value or ""))


def format_phone(value):
    """'44999999999' -> '(44) 99999-9999' | '4433334444' -> '(44) 3333-4444'"""
    d = only_digits(value)
    if len(d) == PHONE_DIGITS:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == LANDLINE_DIGITS:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return value


def format_cpf(value):
    """'12345678901' -> '123.456.789-01'"""
    d = only_digits(value)
    if len(d) != CPF_DIGITS:
        return value
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def format_cnpj(value):
    """'12345678000199' -> '12.345.678/0001-99'"""
    d = only_digits(value)
    if len(d) != CNPJ_DIGITS:
        return value
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def format_cpf_cnpj(value):
    """Escolhe a máscara pelo tamanho: 11 dígitos = CPF, 14 = CNPJ."""
    d = only_digits(value)
    if len(d) == CPF_DIGITS:
        return format_cpf(d)
    if len(d) == CNPJ_DIGITS:
        return format_cnpj(d)
    return value
