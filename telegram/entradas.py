"""
O que a pessoa digita no bot, convertido para valores. Funções puras: recebem o texto e
devolvem o valor, ou levantam EntradaInvalida com o exemplo do formato certo.
"""
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

TERMO_MAX = 30
TEXTO_MAX = 200

DICA_DATA = "Não entendi a data. Use dd/mm/aaaa, dd/mm, hoje, ontem, anteontem ou amanhã. Exemplo: 03/10/2026"
DICA_VALOR = "Não entendi o valor. Use vírgula nos centavos. Exemplo: 1.234,56"
DICA_QUANTIDADE = "Não entendi a quantidade. Use um número inteiro a partir de 1. Exemplo: 3"
DICA_NUMERO = "Não entendi o número. Exemplo: 128"
DICA_TEXTO = "Não entendi. Digite um texto de até {} caracteres.".format(TEXTO_MAX)
DICA_TERMO = "Digite pelo menos 2 letras ou 3 números, com até {} caracteres. Exemplo: caderno".format(TERMO_MAX)

DIAS = {"hoje": 0, "ontem": -1, "anteontem": -2, "amanha": 1}
DATA_BR = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?$")
DATA_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
VALOR_BR = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")  # 1.234,56 · 1234,5 · 50 · 1.234
VALOR_PONTO = re.compile(r"^(\d+)\.(\d{1,2})$")  # 50.5 · 50.50
QUANTIDADE = re.compile(r"^(\d{1,9})\s*(?:x|vezes|parcelas?|unidades?|un)?$")
NUMERO = re.compile(r"^(?:pedido\s*)?(?:n[º°o.]?\s*|#\s*)?(\d{1,9})$")


class EntradaInvalida(ValueError):
    """O texto não pôde ser interpretado. A mensagem já diz o formato certo."""


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def interpretar_data(texto, hoje=None):
    """dd/mm, dd/mm/aa, dd/mm/aaaa, aaaa-mm-dd, hoje, ontem, anteontem ou amanhã."""
    hoje = hoje or timezone.localdate()
    limpo = _sem_acento(texto.strip().lower())
    if limpo in DIAS:
        return hoje + timedelta(days=DIAS[limpo])
    iso, br = DATA_ISO.match(limpo), DATA_BR.match(limpo)
    if iso:
        ano, mes, dia = (int(parte) for parte in iso.groups())
    elif br:
        dia, mes = int(br[1]), int(br[2])
        ano = hoje.year if br[3] is None else int(br[3]) + (2000 if len(br[3]) == 2 else 0)
    else:
        raise EntradaInvalida(DICA_DATA)
    try:
        return date(ano, mes, dia)
    except ValueError:
        raise EntradaInvalida(DICA_DATA) from None


def interpretar_valor(texto):
    """1.234,56 · R$ 50 · 50,5 · 50.5. Ponto seguido de 3 dígitos é separador de milhar (1.234 = mil)."""
    limpo = texto.strip().lower().replace(" ", "").removeprefix("r$")
    ponto = VALOR_PONTO.match(limpo)
    if ponto:
        return Decimal("{}.{}".format(ponto[1], ponto[2])).quantize(Decimal("0.01"))
    br = VALOR_BR.match(limpo)
    if not br:
        raise EntradaInvalida(DICA_VALOR)
    return Decimal("{}.{}".format(br[1].replace(".", ""), br[2] or "0")).quantize(Decimal("0.01"))


def interpretar_quantidade(texto):
    """3 · 3x · 3 parcelas · 3 un. Inteiro a partir de 1."""
    casou = QUANTIDADE.match(texto.strip().lower())
    if not casou or int(casou[1]) < 1:
        raise EntradaInvalida(DICA_QUANTIDADE)
    return int(casou[1])


def interpretar_numero(texto):
    """Número de um registro: 128 · #128 · nº 128 · pedido 128."""
    casou = NUMERO.match(texto.strip().lower())
    if not casou or int(casou[1]) < 1:
        raise EntradaInvalida(DICA_NUMERO)
    return int(casou[1])


def interpretar_texto(texto):
    """Texto livre (ex.: um nome): sem espaços sobrando, não vazio e com até TEXTO_MAX caracteres."""
    limpo = " ".join(texto.split())
    if not limpo or len(limpo) > TEXTO_MAX:
        raise EntradaInvalida(DICA_TEXTO)
    return limpo


def interpretar_termo(texto):
    """Termo de busca: pelo menos 2 letras ou 3 números. Espaços repetidos viram um só."""
    termo = " ".join(texto.split())
    letras = sum(caractere.isalpha() for caractere in termo)
    numeros = sum(caractere.isdigit() for caractere in termo)
    if len(termo) > TERMO_MAX or (letras < 2 and numeros < 3):
        raise EntradaInvalida(DICA_TERMO)
    return termo
