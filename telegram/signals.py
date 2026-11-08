"""
O cartão no Telegram acompanha a importação: quando ela muda pelo site, pela leitura da IA ou
pela manutenção, o cartão é redesenhado. O que o próprio bot mudou ele já redesenhou na ação.
"""
import logging

from django.dispatch import receiver

from importacao.services import importacao_alterada

from . import importacoes

logger = logging.getLogger(__name__)

AVISO_SITE = "🌐 Alterado no site."
CANAL_DO_BOT = "telegram"


@receiver(importacao_alterada, dispatch_uid="telegram_redesenhar_cartao")
def redesenhar_cartao(sender, importacao, situacao_anterior, por, canal, **kwargs):
    if canal == CANAL_DO_BOT:
        return  # não edita duas vezes o que o bot acabou de desenhar
    try:
        importacoes.atualizar_cartao(importacao, AVISO_SITE if canal == "site" else "")
    except Exception:
        # Avisar o Telegram é secundário: nunca derruba quem mudou a importação
        logger.exception("Falha ao redesenhar o cartão da importação %s.", importacao.pk)
