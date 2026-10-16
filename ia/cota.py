"""
Cota mensal de tokens. O dono da cota é o usuário (ver docs/plano-app-ia.md).

O consumo fica em ConsumoIA, uma linha por (usuário, mês): a cota "zera" sozinha
na virada do mês, sem cron e sem contador para reiniciar.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import F, Sum
from django.utils import timezone

from .models import ConfiguracaoIA, ConfiguracaoIAUsuario, ConsumoIA
from .provedores.base import ErroIA

FUSO = ZoneInfo("America/Sao_Paulo")
MILHAO = Decimal("1000000")


class CotaExcedida(ErroIA):
    situacao = "bloqueada_cota"

    def __init__(self, situacao_cota):
        super().__init__(situacao_cota.mensagem_esgotada())
        self.situacao_cota = situacao_cota


@dataclass(frozen=True)
class SituacaoCota:
    usado: int
    limite: int
    restante: int
    percentual: int
    renova_em: date
    esgotada: bool
    em_alerta: bool

    def mensagem_esgotada(self):
        return "Sua cota de IA acabou. Ela renova em {:%d/%m}.".format(self.renova_em)


def mes_atual():
    """Dia 1 do mês de hoje em America/Sao_Paulo, mesmo com o servidor em UTC."""
    return timezone.now().astimezone(FUSO).date().replace(day=1)


def proximo_mes(mes):
    return date(mes.year + mes.month // 12, mes.month % 12 + 1, 1)


def dono_da_cota(usuario):
    return usuario


def limite_do_usuario(usuario):
    """Limite próprio do usuário, se houver; senão o padrão da configuração. Lido a cada chamada."""
    limite = ConfiguracaoIAUsuario.objects.filter(usuario=usuario).values_list("limite_mensal", flat=True).first()
    if limite is None:
        return ConfiguracaoIA.obter().limite_mensal_usuario
    return limite


def situacao_da_cota(dono):
    config = ConfiguracaoIA.obter()
    mes = mes_atual()
    usado = ConsumoIA.objects.filter(usuario=dono, mes=mes).values_list("tokens_total", flat=True).first() or 0
    limite = limite_do_usuario(dono)
    restante = max(limite - usado, 0)
    percentual = usado * 100 // limite if limite else 100
    return SituacaoCota(
        usado=usado,
        limite=limite,
        restante=restante,
        percentual=percentual,
        renova_em=proximo_mes(mes),
        esgotada=limite == 0 or restante < config.reserva_minima_tokens,
        em_alerta=percentual >= config.aviso_percentual,
    )


def verificar(dono):
    """Levanta CotaExcedida se o dono não tiver saldo; senão devolve a SituacaoCota."""
    situacao = situacao_da_cota(dono)
    if situacao.esgotada:
        raise CotaExcedida(situacao)
    return situacao


def teto_do_sistema_atingido():
    """Soma o mês de todos os usuários e compara com limite_mensal_sistema (0 = sem teto)."""
    limite = ConfiguracaoIA.obter().limite_mensal_sistema
    if not limite:
        return False
    usado = ConsumoIA.objects.filter(mes=mes_atual()).aggregate(total=Sum("tokens_total"))["total"] or 0
    return usado >= limite


def calcular_custo(uso, config):
    """Custo estimado em US$: tokens x preço por milhão. Sem preço cadastrado, conta 0."""
    entrada = uso.entrada * (config.preco_entrada_milhao or 0)
    saida = uso.saida * (config.preco_saida_milhao or 0)
    return (Decimal(entrada) + Decimal(saida)) / MILHAO


def registrar_consumo(dono, uso, custo):
    """Soma o uso na linha do mês com F(): duas chamadas simultâneas não perdem tokens."""
    linha, _ = ConsumoIA.objects.get_or_create(usuario=dono, mes=mes_atual())
    ConsumoIA.objects.filter(pk=linha.pk).update(
        tokens_entrada=F("tokens_entrada") + uso.entrada,
        tokens_saida=F("tokens_saida") + uso.saida,
        tokens_total=F("tokens_total") + uso.total,
        custo_estimado=F("custo_estimado") + custo,
        requisicoes=F("requisicoes") + 1,
    )
