"""
Botões do bot. O callback_data tem a forma "acao:id[:argumento...]", com códigos curtos
(até 64 bytes). Cada ação busca o registro pelo que o vínculo de quem tocou pode ver, a
mensagem é redesenhada no lugar e o toque é respondido uma única vez.
"""
from django.core.exceptions import PermissionDenied

from importacao import services as importacao_services
from importacao.importadores import AjusteInvalido, ImportacaoInvalida
from importacao.models import Importacao

from . import conversa, importacoes, services, telas
from .cliente import contexto_do_log, obter_cliente
from .models import EsperaTelegram, ImportacaoTelegram

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
    importacao = conversa.importacao_da_espera(espera)
    conversa.cancelar(vinculo, apagar_pergunta=False)
    # A pergunta de um campo da importação ocupou o cartão: cancelar devolve o cartão
    return telas.desenhar(importacao) if importacao else telas.Tela(conversa.PERGUNTA_CANCELADA)


# ─── Importação de documentos (só por importacao/services.py) ─────────────────

FALHAS_DA_IMPORTACAO = (
    importacao_services.AcaoInvalida, importacao_services.ImportacaoRecusada, AjusteInvalido, PermissionDenied,
)


def _importacao(vinculo, texto_id, callback):
    """A importação do botão, buscada entre as de quem tocou: a de outra pessoa é "botão antigo"."""
    importacao = Importacao.objects.filter(pk=_inteiro(texto_id), criado_por=vinculo.usuario).first()
    if importacao is None:
        raise telas.Recusa(BOTAO_ANTIGO)
    # A mensagem tocada passa a ser o cartão vivo, que o sinal edita
    mensagem = callback["message"]
    importacoes.guardar_cartao(importacao, mensagem["chat"]["id"], mensagem)
    return importacao


def _campo(importacao, codigo):
    importador = importacao.importador
    campo = next((campo for campo in importador.campos() if campo.codigo == codigo), None) if importador else None
    if campo is None or importacao.situacao != Importacao.Situacao.PRONTA:
        raise telas.Recusa(BOTAO_ANTIGO)
    return campo


def explicar_recusa(erro, importador):
    """O que faltou no form do app, dizendo qual botão do cartão resolve."""
    campos = {campo.codigo: campo for campo in importador.campos()} if importador else {}
    erros = erro.erros if hasattr(erro.erros, "items") else {"__all__": [erro.erros]}
    partes = []
    for nome, mensagens in erros.items():
        if isinstance(mensagens, (list, tuple)):
            texto = " ".join(str(mensagem) for mensagem in mensagens)
        else:
            texto = str(mensagens)
        campo = campos.get(nome)
        if campo:
            partes.append("{}: {} Toque em ✏️ {}.".format(campo.rotulo, texto, campo.rotulo))
        else:
            partes.append("{} Corrija em 🌐 Editar no site.".format(texto))
    return "Não deu para cadastrar. " + " ".join(partes)


def _executar(funcao, *args):
    try:
        return funcao(*args)
    except FALHAS_DA_IMPORTACAO as erro:
        raise telas.Recusa(str(erro)) from None


def _confirmar(vinculo, argumentos, callback):  # ok:<importação>
    importacao = _importacao(vinculo, argumentos, callback)
    try:
        importacao = _executar(importacao_services.confirmar_importacao, importacao, vinculo.usuario, "telegram")
    except ImportacaoInvalida as erro:
        raise telas.Recusa(explicar_recusa(erro, importacao.importador)) from None
    return telas.desenhar(importacao)


def _descartar(vinculo, argumentos, callback):  # dc:<importação>
    importacao = _importacao(vinculo, argumentos, callback)
    return telas.desenhar(_executar(importacao_services.descartar_importacao, importacao, vinculo.usuario, "telegram"))


def _escolher_tipo(vinculo, argumentos, callback):  # it:<importação>:<tipo>
    numero, tipo = _partes(argumentos, 2)
    importacao = _importacao(vinculo, numero, callback)
    importacao = _executar(importacao_services.escolher_tipo, importacao, tipo, vinculo.usuario, "telegram")
    importacoes.agendar(importacao)
    return telas.desenhar(importacao)


def _tentar_de_novo(vinculo, argumentos, callback):  # tn:<importação>
    importacao = _importacao(vinculo, argumentos, callback)
    if not ImportacaoTelegram.objects.filter(importacao=importacao).exclude(file_id="").exists():
        raise telas.Recusa("Este arquivo foi enviado pelo site. Para ler de novo, use a tela da importação no site.")
    importacao = _executar(importacao_services.preparar_nova_tentativa, importacao, vinculo.usuario, "telegram")
    importacoes.agendar(importacao)
    return telas.desenhar(importacao)


def _abrir_campo(vinculo, argumentos, callback):  # ic:<importação>:<campo>
    numero, codigo = _partes(argumentos, 2)
    importacao = _importacao(vinculo, numero, callback)
    campo = _campo(importacao, codigo)
    if campo.tipo == "escolha":
        return telas.opcoes_do_campo(importacao, campo, vinculo.usuario)
    mensagem = callback["message"]
    conversa.pedir_campo_da_importacao(vinculo, importacao, campo, mensagem["chat"]["id"], mensagem["message_id"])
    # A pergunta já ocupou a mensagem do cartão: nada a redesenhar


def _pagina_de_opcoes(vinculo, argumentos, callback):  # il:<importação>:<campo>:<página>
    numero, codigo, pagina = _partes(argumentos, 3)
    importacao = _importacao(vinculo, numero, callback)
    return telas.opcoes_do_campo(importacao, _campo(importacao, codigo), vinculo.usuario, _inteiro(pagina))


def _escolher_opcao(vinculo, argumentos, callback):  # io:<importação>:<campo>:<opção>
    numero, codigo, escolhida = _partes(argumentos, 3)
    importacao = _importacao(vinculo, numero, callback)
    campo = _campo(importacao, codigo)
    # Só vale uma opção da lista: um cliente modificado pode mandar qualquer id
    opcao = next((opcao for opcao in campo.opcoes(vinculo.usuario, importacao.escopo) if str(opcao[0]) == escolhida), None)
    if opcao is None:
        raise telas.Recusa(BOTAO_ANTIGO)
    importacao, mensagem = _executar(
        importacao_services.atualizar_dados, importacao, codigo, opcao[0], vinculo.usuario, "telegram",
    )
    return telas.desenhar(importacao, "✅ " + mensagem if mensagem else "")


def _voltar_ao_cartao(vinculo, argumentos, callback):  # iv:<importação>
    return telas.desenhar(_importacao(vinculo, argumentos, callback))


def _reabrir(vinculo, argumentos, callback):  # ab:<importação>
    importacao = Importacao.objects.filter(pk=_inteiro(argumentos), criado_por=vinculo.usuario).first()
    if importacao is None:
        raise telas.Recusa(BOTAO_ANTIGO)
    importacoes.reabrir_cartao(importacao, callback["message"]["chat"]["id"])
    # O cartão foi para o fim do chat; a lista de pendentes fica como está


def _pendentes(vinculo, argumentos, callback):  # pd:<página>
    return telas.pendentes(vinculo.usuario, _inteiro(argumentos))


# código do callback_data -> função(vinculo, argumentos, callback) que devolve a Tela nova, ou None
ACOES = {
    "ok": _confirmar,
    "dc": _descartar,
    "it": _escolher_tipo,
    "tn": _tentar_de_novo,
    "ic": _abrir_campo,
    "il": _pagina_de_opcoes,
    "io": _escolher_opcao,
    "iv": _voltar_ao_cartao,
    "ab": _reabrir,
    "pd": _pendentes,
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
