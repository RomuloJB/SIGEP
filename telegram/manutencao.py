"""
Limpeza periódica do bot. Usada pelo comando `manage.py telegram_limpar` e pela rota interna
/telegram/manutencao/ (chamada pelo cron diário do App Engine).
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import CodigoVinculoTelegram, ConfiguracaoTelegram, LimiteTelegram, MensagemTelegram

logger = logging.getLogger(__name__)

TAMANHO_LOTE = 1000
CONTADOR_PARADO_DIAS = 7


def _em_lotes(queryset, acao, tamanho_lote):
    """Aplica `acao` aos registros em lotes, para não prender a tabela numa transação longa."""
    total, ultimo = 0, 0
    while True:
        lote = list(queryset.filter(pk__gt=ultimo).order_by("pk").values_list("pk", flat=True)[:tamanho_lote])
        if not lote:
            return total
        total += acao(queryset.model.objects.filter(pk__in=lote))
        ultimo = lote[-1]


def _apagar(lote):
    return lote.delete()[0]


def limpar(tamanho_lote=TAMANHO_LOTE):
    """Aplica os prazos da ConfiguracaoTelegram e devolve quantos registros foram tratados de cada tipo."""
    config = ConfiguracaoTelegram.obter()
    agora = timezone.now()

    mensagens = MensagemTelegram.objects.filter(criado_em__lt=agora - timedelta(days=config.reter_mensagens_dias))
    conteudos = MensagemTelegram.objects.filter(
        criado_em__lt=agora - timedelta(days=config.reter_conteudo_dias), conteudo__isnull=False,
    )
    # Um bloqueio ainda valendo não some só porque a pessoa parou de mandar mensagens
    contadores = LimiteTelegram.objects.filter(
        ultima_vez__lt=agora - timedelta(days=CONTADOR_PARADO_DIAS),
    ).exclude(bloqueado_ate__gt=agora)
    codigos = CodigoVinculoTelegram.objects.filter(expira_em__lt=agora)

    resultado = {
        # As mensagens vêm antes: não adianta limpar o JSON de quem vai ser apagado
        "mensagens_apagadas": _em_lotes(mensagens, _apagar, tamanho_lote),
        "conteudos_apagados": _em_lotes(conteudos, lambda lote: lote.update(conteudo=None), tamanho_lote),
        "contadores_apagados": _em_lotes(contadores, _apagar, tamanho_lote),
        "codigos_apagados": _em_lotes(codigos, _apagar, tamanho_lote),
    }
    logger.info("Limpeza do Telegram: %s", resultado)
    return resultado
