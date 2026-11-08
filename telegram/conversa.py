"""
Perguntas do bot. Cada update é uma requisição separada, então a "memória" de que o bot fez
uma pergunta fica no banco, numa EsperaTelegram (uma por pessoa; a nova substitui a anterior).
"""
from dataclasses import dataclass, replace
from datetime import timedelta
from html import escape
from typing import Callable

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from importacao import services as importacao_services
from importacao.importadores import AjusteInvalido
from importacao.models import Importacao

from . import entradas, importacoes, telas
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


# Campos da importação: o código da espera é "i:<código do Campo>" e a referência é a importação
PREFIXO_IMPORTACAO = "i:"
ENTRADAS_DO_CAMPO = {
    "texto": (entradas.interpretar_texto, "Digite o texto correto."),
    "data": (entradas.interpretar_data, "Digite a data: dd/mm/aaaa, hoje ou ontem."),
    "valor": (entradas.interpretar_valor, "Digite o valor. Exemplo: 1.234,56"),
    "inteiro": (entradas.interpretar_quantidade, "Digite um número inteiro. Exemplo: 3"),
}


def _contexto(vinculo):
    return contexto_do_log(vinculo.telegram_id, vinculo, "texto")


def pedir(vinculo, campo, chat_id, mensagem_id=None, pergunta=None, referencia=None):
    """
    Faz a pergunta, com o botão Cancelar, e passa a esperar o texto. Com mensagem_id, a
    mensagem do botão tocado vira a pergunta. A pergunta anterior, se houver, é apagada.
    `referencia` é o registro que a resposta vai alterar (ex.: a importação).
    """
    cliente = obter_cliente()
    contexto = _contexto(vinculo)
    texto, teclado = pergunta or CAMPOS_TEXTO[campo].pergunta, [[botao("✖️ Cancelar", "cx")]]
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
        "referencia_tipo": ContentType.objects.get_for_model(referencia) if referencia else None,
        "referencia_id": referencia.pk if referencia else None,
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
    campo = campo_da_espera(espera)
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
    enviada = cliente.enviar(chat_id, tela.texto, tela.teclado, contexto=contexto)
    if tela.ao_enviar and isinstance(enviada, dict):
        tela.ao_enviar(enviada)


def cancelar(vinculo, apagar_pergunta=True):
    """Apaga a espera da pessoa e, se pedido, a mensagem da pergunta. Devolve True se havia uma."""
    espera = EsperaTelegram.objects.filter(vinculo=vinculo).first()
    if espera is None:
        return False
    espera.delete()
    if apagar_pergunta and espera.mensagem_pergunta_id:
        obter_cliente().apagar(vinculo.chat_id, espera.mensagem_pergunta_id, contexto=_contexto(vinculo))
    return True


# ─── Campos da importação ─────────────────────────────────────────────────────

def pedir_campo_da_importacao(vinculo, importacao, campo, chat_id, mensagem_id):
    """Transforma o cartão na pergunta do campo; a resposta é interpretada pelo tipo do Campo."""
    _, dica = ENTRADAS_DO_CAMPO[campo.tipo]
    pergunta = "✏️ <b>{}</b> · importação nº {}\n{}".format(escape(campo.rotulo), importacao.pk, dica)
    pedir(vinculo, PREFIXO_IMPORTACAO + campo.codigo, chat_id, mensagem_id, pergunta=pergunta, referencia=importacao)


def importacao_da_espera(espera):
    """A importação que a espera vai alterar, se ainda for de quem responde. Senão, None."""
    if not espera.campo.startswith(PREFIXO_IMPORTACAO):
        return None
    importacao = espera.referencia
    if not isinstance(importacao, Importacao) or importacao.criado_por_id != espera.vinculo.usuario_id:
        return None
    return importacao


def campo_da_espera(espera):
    """O CampoTexto que trata a resposta: um dos fixos ou o campo de uma importação."""
    if espera.campo in CAMPOS_TEXTO:
        return CAMPOS_TEXTO[espera.campo]
    importacao = importacao_da_espera(espera)
    importador = importacao.importador if importacao else None
    if importador is None:
        return None
    codigo = espera.campo[len(PREFIXO_IMPORTACAO):]
    campo = next((campo for campo in importador.campos() if campo.codigo == codigo), None)
    if campo is None or campo.tipo not in ENTRADAS_DO_CAMPO:
        return None
    interpretar, dica = ENTRADAS_DO_CAMPO[campo.tipo]
    return CampoTexto(dica, interpretar, _aplicar_no_rascunho(importacao, codigo))


def _aplicar_no_rascunho(importacao, codigo):
    def responder(vinculo, valor):
        try:
            atualizada, mensagem = importacao_services.atualizar_dados(importacao, codigo, valor, vinculo.usuario, "telegram")
        except (AjusteInvalido, importacao_services.AcaoInvalida) as erro:
            raise telas.Recusa(str(erro))
        tela = telas.desenhar(atualizada, "✅ " + mensagem if mensagem else "")
        # O cartão volta no fim do chat: é a mensagem nova que o sinal passa a editar
        return replace(tela, ao_enviar=lambda enviada: importacoes.guardar_cartao(atualizada, vinculo.chat_id, enviada))
    return responder
