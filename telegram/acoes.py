"""
Botões do bot. O callback_data tem a forma "acao:id[:argumento...]", com códigos curtos
(até 64 bytes). Cada ação busca o registro pelo que o vínculo de quem tocou pode ver, a
mensagem é redesenhada no lugar e o toque é respondido uma única vez.
"""
from . import conversa, services, telas
from .cliente import contexto_do_log, obter_cliente
from .models import EsperaTelegram

BOTAO_ANTIGO = "Botão antigo. Abra de novo."
SEM_ACESSO_EMPRESA = "Você não tem acesso a esta empresa."


def _inteiro(texto):
    # Um cliente modificado pode mandar qualquer coisa no callback_data
    try:
        return int(texto)
    except (TypeError, ValueError):
        raise telas.Recusa(BOTAO_ANTIGO) from None


def _partes(argumentos, quantas):
    """Divide os argumentos; o último pode conter ":" (o termo de uma busca)."""
    partes = argumentos.split(":", quantas - 1)
    return partes + [""] * (quantas - len(partes))


def _aprovacoes(vinculo, argumentos, callback):  # ap:<página>
    return telas.aprovacoes(vinculo, _inteiro(argumentos))


def _pedido(vinculo, argumentos, callback):  # p:<pedido>:<página da lista>
    numero, pagina = _partes(argumentos, 2)
    return telas.pedido(vinculo, _inteiro(numero), _inteiro(pagina or "0"))


def _estoque(vinculo, argumentos, callback):  # es:<página>:<termo>
    pagina, termo = _partes(argumentos, 2)
    return telas.estoque(vinculo, termo, _inteiro(pagina))


def _produto(vinculo, argumentos, callback):  # pr:<produto>:<página>:<termo>
    produto, pagina, termo = _partes(argumentos, 3)
    return telas.produto(vinculo, _inteiro(produto), _inteiro(pagina), termo)


def _buscar_produto(vinculo, argumentos, callback):  # bp
    mensagem = callback["message"]
    conversa.pedir(vinculo, "busca", mensagem["chat"]["id"], mensagem["message_id"])
    # A pergunta já ocupou a mensagem do botão: nada a redesenhar


def _empresas(vinculo, argumentos, callback):  # ep:<página>
    return telas.empresas(vinculo, _inteiro(argumentos))


def _escolher_empresa(vinculo, argumentos, callback):  # em:<empresa>
    empresa = services.escolher_empresa(vinculo, _inteiro(argumentos))
    if empresa is None:
        raise telas.Recusa(SEM_ACESSO_EMPRESA)
    return telas.empresa_escolhida(empresa)


def _cancelar_pergunta(vinculo, argumentos, callback):  # cx
    espera = EsperaTelegram.objects.filter(vinculo=vinculo).first()
    if espera is None or espera.mensagem_pergunta_id != callback["message"]["message_id"]:
        raise telas.Recusa(BOTAO_ANTIGO)
    conversa.cancelar(vinculo, apagar_pergunta=False)
    return telas.Tela(conversa.PERGUNTA_CANCELADA)


# código do callback_data -> função(vinculo, argumentos, callback) que devolve a Tela nova, ou None
ACOES = {
    "ap": _aprovacoes,
    "p": _pedido,
    "es": _estoque,
    "pr": _produto,
    "bp": _buscar_produto,
    "ep": _empresas,
    "em": _escolher_empresa,
    "cx": _cancelar_pergunta,
}


def _redesenhar(mensagem, tela, contexto):
    """Edita a mensagem do botão; se não der (apagada, antiga demais), manda a tela como mensagem nova."""
    cliente = obter_cliente()
    chat_id = mensagem["chat"]["id"]
    if cliente.editar(chat_id, mensagem["message_id"], tela.texto, tela.teclado, contexto=contexto) is None:
        cliente.enviar(chat_id, tela.texto, tela.teclado, contexto=contexto)


def despachar(callback, registro):
    """
    Roda a ação do botão e responde o toque uma única vez: em branco quando dá certo, com
    alerta quando é recusado. `registro` é a entrada do update no log (MensagemTelegram).
    """
    cliente = obter_cliente()
    telegram_id = callback["from"]["id"]
    vinculo = services.vinculo_valido(telegram_id)
    contexto = contexto_do_log(telegram_id, vinculo, "botao")
    nome, _, argumentos = callback.get("data", "").partition(":")
    acao = ACOES.get(nome)
    try:
        if vinculo is None or acao is None:
            raise telas.Recusa(BOTAO_ANTIGO)
        tela = acao(vinculo, argumentos, callback)
    except telas.Recusa as recusa:
        cliente.responder_botao(callback["id"], str(recusa), alerta=True, contexto=contexto)
        return
    except Exception:
        # Libera o botão e deixa o erro seguir para o log e para o aviso de erro
        cliente.responder_botao(callback["id"], contexto=contexto)
        raise
    if tela is not None:
        _redesenhar(callback["message"], tela, contexto)
    cliente.responder_botao(callback["id"], contexto=contexto)
