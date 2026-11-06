"""Decide quem atende cada update. Não tem regra de negócio: só encaminha."""
from . import acoes, comandos, conversa, limites, services
from .cliente import contexto_do_log, obter_cliente
from .models import MensagemTelegram

ARQUIVO_SEM_USO = "Recebi o arquivo, mas ainda não sei o que fazer com ele."


def tem_arquivo(mensagem):
    return "photo" in mensagem or "document" in mensagem


def eh_comando(mensagem):
    return mensagem.get("text", "").startswith("/")


def _avisar_conexao(mensagem):
    telegram_id = mensagem["from"]["id"]
    if limites.pode_avisar_conexao(telegram_id):
        obter_cliente().enviar(
            mensagem["chat"]["id"], comandos.COMO_CONECTAR, teclado=comandos.teclado_do_site(),
            contexto=contexto_do_log(telegram_id, tipo="aviso"),
        )


def _rotear(update, vinculo):
    if "callback_query" in update:
        acoes.despachar(update["callback_query"], vinculo)
        return

    mensagem = update["message"]
    comando = eh_comando(mensagem)
    if comando and comandos.executar(mensagem, vinculo):
        return
    if vinculo is None:
        _avisar_conexao(mensagem)
        return

    resposta = comandos.AJUDA
    if tem_arquivo(mensagem):
        resposta = ARQUIVO_SEM_USO
    elif mensagem.get("text") and not comando:
        espera = conversa.espera_ativa(vinculo)
        if espera:
            conversa.receber_texto(mensagem, espera)
            return
    obter_cliente().enviar(
        mensagem["chat"]["id"], resposta, contexto=contexto_do_log(mensagem["from"]["id"], vinculo, "texto"),
    )


def processar(update, registro):
    vinculo = services.vinculo_valido(registro.telegram_id)
    if vinculo:
        services.registrar_uso(vinculo, registro.chat_id)
    _rotear(update, vinculo)
    registro.situacao = MensagemTelegram.Situacao.PROCESSADA
    registro.erro = ""
    registro.save(update_fields=["situacao", "erro"])
