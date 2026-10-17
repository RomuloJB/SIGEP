"""
Limpeza periódica da auditoria da IA. Usada pelo comando `manage.py ia_limpar`
e pela rota interna /ia/manutencao/ (chamada pelo agendador diário).
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import ConfiguracaoIA, RequisicaoIA

logger = logging.getLogger(__name__)

TAMANHO_LOTE = 1000


def limpar_requisicoes(tamanho_lote=TAMANHO_LOTE):
    """
    Apaga as RequisicaoIA mais antigas que reter_requisicoes_dias, em lotes, e devolve
    quantas apagou. O ConsumoIA não é tocado: a cota do mês continua valendo.
    reter_requisicoes_dias = 0 desliga a limpeza.
    """
    dias = ConfiguracaoIA.obter().reter_requisicoes_dias
    if not dias:
        return 0

    limite = timezone.now() - timedelta(days=dias)
    antigas = RequisicaoIA.objects.filter(criado_em__lt=limite).order_by("pk")
    total = 0
    while True:
        lote = list(antigas.values_list("pk", flat=True)[:tamanho_lote])
        if not lote:
            break
        apagadas, _ = RequisicaoIA.objects.filter(pk__in=lote).delete()
        total += apagadas
    logger.info("Limpeza da IA: %s requisições apagadas (mais antigas que %s dias).", total, dias)
    return total
