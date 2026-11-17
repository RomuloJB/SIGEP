"""
Busca geral da lista de importações (campo "Buscar" do card, ?q=): procura em todos os
registros, não só na página atual. Versão enxuta do website/busca.py, que o resto do
site usa: o app importacao não importa apps do projeto (test_contrato.IsolamentoTestCase).

Cada palavra precisa aparecer no arquivo, no tipo, no rótulo da origem ou da situação,
ou ser o número da importação ("12" ou "#12"). Sem diferenciar maiúsculas e acentos.
"""
import unicodedata

from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Lower

from .models import Importacao

PARAMETRO = "q"
TAMANHO_MAXIMO = 100

COM_ACENTO = "áàâãäéèêëíìîïóòôõöúùûüçñ"
SEM_ACENTO = "aaaaaeeeeiiiiooooouuuucn"
MAIOR_INTEIRO = 2 ** 63 - 1

CAMPOS_DE_TEXTO = ("arquivo_nome", "tipo")
CAMPOS_COM_ROTULO = {"origem": Importacao.Origem, "situacao": Importacao.Situacao}


def sem_acento(texto):
    decomposto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def coluna_sem_acento(campo):
    """A coluna em minúsculas e sem acentos (TRANSLATE do Postgres, sem extensão)."""
    return Func(Lower(F(campo)), Value(COM_ACENTO), Value(SEM_ACENTO), function="TRANSLATE", output_field=CharField())


def buscar_importacoes(queryset, termo):
    palavras = [sem_acento(p) for p in termo.split()]
    if not palavras:
        return queryset

    queryset = queryset.alias(**{"_busca_" + campo: coluna_sem_acento(campo) for campo in CAMPOS_DE_TEXTO})
    for palavra in palavras:
        condicao = Q()
        for campo in CAMPOS_DE_TEXTO:
            condicao |= Q(**{"_busca_{}__contains".format(campo): palavra})
        for campo, escolhas in CAMPOS_COM_ROTULO.items():
            valores = [valor for valor, rotulo in escolhas.choices if palavra in sem_acento(rotulo)]
            if valores:
                condicao |= Q(**{campo + "__in": valores})
        numero = palavra.lstrip("#")
        if numero.isdigit() and int(numero) <= MAIOR_INTEIRO:
            condicao |= Q(pk=int(numero))
        queryset = queryset.filter(condicao)
    return queryset
