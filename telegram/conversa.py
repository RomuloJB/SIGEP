"""Perguntas do bot: enquanto houver uma EsperaTelegram, o próximo texto da pessoa é a resposta."""
from .cliente import contexto_do_log, obter_cliente
from .models import EsperaTelegram

PERGUNTA_SEM_USO = "Essa pergunta não vale mais."

# campo da espera -> função(mensagem, espera). Cada funcionalidade registra as suas aqui.
RESPOSTAS = {}


def espera_ativa(vinculo):
    return EsperaTelegram.objects.filter(vinculo=vinculo).first()


def receber_texto(mensagem, espera):
    responder = RESPOSTAS.get(espera.campo)
    if responder is not None:
        responder(mensagem, espera)
        return
    # Sem isso a pessoa ficaria presa numa pergunta que o bot não sabe mais tratar
    vinculo = espera.vinculo
    espera.delete()
    obter_cliente().enviar(
        mensagem["chat"]["id"], PERGUNTA_SEM_USO, contexto=contexto_do_log(mensagem["from"]["id"], vinculo, "texto"),
    )


def cancelar(vinculo):
    """Apaga a espera da pessoa. Devolve True se havia uma."""
    apagados, _ = EsperaTelegram.objects.filter(vinculo=vinculo).delete()
    return apagados > 0
