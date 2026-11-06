from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from telegram import recebimento
from telegram.cliente import obter_cliente
from telegram.models import ConfiguracaoTelegram, VinculoTelegram

TELEGRAM_ANA = 9_000_000_001
TELEGRAM_BIA = 9_000_000_002


def pessoa(telegram_id=TELEGRAM_ANA):
    return {"id": telegram_id, "is_bot": False, "first_name": "Ana", "last_name": "Souza", "username": "ana_tg"}


def update(texto=None, update_id=1, telegram_id=TELEGRAM_ANA, tipo_chat="private", **campos):
    """Update de mensagem. `campos` vão dentro dela, como photo=[...] ou document={...}."""
    mensagem = {
        "message_id": update_id,
        "from": pessoa(telegram_id),
        "chat": {"id": telegram_id, "type": tipo_chat},
        **campos,
    }
    if texto is not None:
        mensagem["text"] = texto
    return {"update_id": update_id, "message": mensagem}


def clique(data, update_id=1, telegram_id=TELEGRAM_ANA, tipo_chat="private"):
    """Update de botão apertado. A mensagem do botão é do bot, por isso não conta como comando."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "clique-{}".format(update_id),
            "from": pessoa(telegram_id),
            "data": data,
            "message": {"message_id": 99, "chat": {"id": telegram_id, "type": tipo_chat}, "text": "/pergunta do bot"},
        },
    }


class BotTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        self.cliente = obter_cliente()
        self.cliente.limpar()
        self.ana = User.objects.create_user("ana", password="x")
        self.bia = User.objects.create_user("bia", password="x")
        self.proximo_update = 0

    def novo_update_id(self):
        self.proximo_update += 1
        return self.proximo_update

    def enviar(self, texto=None, **kwargs):
        """Passa o texto pelo bot e devolve a última resposta, ou None se não houver nenhuma."""
        recebimento.receber(update(texto, update_id=self.novo_update_id(), **kwargs))
        return self.cliente.mensagens[-1] if self.cliente.mensagens else None

    def vincular(self, usuario, telegram_id):
        return VinculoTelegram.objects.create(usuario=usuario, telegram_id=telegram_id, chat_id=telegram_id)
