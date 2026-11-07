"""
Perguntas do bot. Cada update é uma requisição separada, então a "memória" de que o bot fez
uma pergunta fica no banco, numa EsperaTelegram (uma por pessoa; a nova substitui a anterior).
"""
from dataclasses import dataclass
from datetime import timedelta
from html import escape
from typing import Callable

from django.utils import timezone

from . import entradas, telas
from .cliente import botao, contexto_do_log, obter_cliente
from .models import ConfiguracaoTelegram, EsperaTelegram

PERGUNTA_SEM_USO = "Essa pergunta não vale mais."
PERGUNTA_CANCELADA = "✖️ Pergunta cancelada."


@dataclass(frozen=True)
class CampoTexto:
    pergunta: str
    interpretar: Callable  # texto -> valor; levanta entradas.EntradaInvalida
    responder: Callable    # (vinculo, valor) -> telas.Tela; levanta telas.Recusa


# código do campo -> o que perguntar, como ler a resposta e o que mostrar depois
CAMPOS_TEXTO = {
    "pedido": CampoTexto("🧾 Qual o número do pedido? Exemplo: 128", entradas.interpretar_numero, telas.pedido),
    "busca": CampoTexto(
        "🔎 Qual produto? Digite parte do nome ou do SKU. Exemplo: caderno", entradas.interpretar_termo, telas.estoque,
    ),
}


def _contexto(vinculo):
    return contexto_do_log(vinculo.telegram_id, vinculo, "texto")


def pedir(vinculo, campo, chat_id, mensagem_id=None):
    """
    Faz a pergunta, com o botão Cancelar, e passa a esperar o texto. Com mensagem_id, a
    mensagem do botão tocado vira a pergunta. A pergunta anterior, se houver, é apagada.
    """
    cliente = obter_cliente()
    contexto = _contexto(vinculo)
    texto, teclado = CAMPOS_TEXTO[campo].pergunta, [[botao("✖️ Cancelar", "cx")]]
    if mensagem_id and cliente.editar(chat_id, mensagem_id, texto, teclado, contexto=contexto) is not None:
        pergunta_id = mensagem_id
    else:
        enviada = cliente.enviar(chat_id, texto, teclado, contexto=contexto)
        pergunta_id = enviada.get("message_id") if isinstance(enviada, dict) else None

    anterior = EsperaTelegram.objects.filter(vinculo=vinculo).first()
    if anterior and anterior.mensagem_pergunta_id not in (None, pergunta_id):
        cliente.apagar(chat_id, anterior.mensagem_pergunta_id, contexto=contexto)
    EsperaTelegram.objects.update_or_create(vinculo=vinculo, defaults={
        "campo": campo, "mensagem_pergunta_id": pergunta_id, "desde": timezone.now(),
        "referencia_tipo": None, "referencia_id": None,
    })


def espera_ativa(vinculo):
    """A espera da pessoa, se ainda estiver no prazo da ConfiguracaoTelegram. Vencida, é apagada."""
    espera = EsperaTelegram.objects.filter(vinculo=vinculo).first()
    if espera is None:
        return None
    if timezone.now() - espera.desde > timedelta(minutes=ConfiguracaoTelegram.obter().espera_minutos):
        espera.delete()
        return None
    espera.vinculo = vinculo  # evita buscar de novo o vínculo que já está carregado
    return espera


def receber_texto(mensagem, espera):
    """
    Interpreta a resposta e mostra o resultado no fim do chat, apagando a pergunta. Resposta
    que não dá para usar recebe a dica do formato, e a espera continua.
    """
    vinculo = espera.vinculo
    chat_id = mensagem["chat"]["id"]
    cliente, contexto = obter_cliente(), _contexto(vinculo)
    campo = CAMPOS_TEXTO.get(espera.campo)
    if campo is None:
        # Sem isso a pessoa ficaria presa numa pergunta que o bot não sabe mais tratar
        espera.delete()
        cliente.enviar(chat_id, PERGUNTA_SEM_USO, contexto=contexto)
        return
    try:
        tela = campo.responder(vinculo, campo.interpretar(mensagem["text"]))
    except (entradas.EntradaInvalida, telas.Recusa) as erro:
        cliente.enviar(chat_id, escape(str(erro), quote=False), contexto=contexto)
        return

    espera.delete()
    if espera.mensagem_pergunta_id:
        cliente.apagar(chat_id, espera.mensagem_pergunta_id, contexto=contexto)
    cliente.enviar(chat_id, tela.texto, tela.teclado, contexto=contexto)


def cancelar(vinculo, apagar_pergunta=True):
    """Apaga a espera da pessoa e, se pedido, a mensagem da pergunta. Devolve True se havia uma."""
    espera = EsperaTelegram.objects.filter(vinculo=vinculo).first()
    if espera is None:
        return False
    espera.delete()
    if apagar_pergunta and espera.mensagem_pergunta_id:
        obter_cliente().apagar(vinculo.chat_id, espera.mensagem_pergunta_id, contexto=_contexto(vinculo))
    return True
