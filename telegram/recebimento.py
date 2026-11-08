"""Entrada do bot: aplica os limites, grava o update no log, descarta os reenvios e chama o roteador."""
import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import limites, roteador, services
from .cliente import contexto_do_log, mascarar, obter_cliente
from .models import MensagemTelegram

logger = logging.getLogger(__name__)

START_COM_CODIGO = re.compile(r"^\s*(/start(?:@\w+)?)\s+\S.*$", re.IGNORECASE | re.DOTALL)
ERRO_GENERICO = "⚠️ Algo deu errado. Já registramos o problema."
INTERROMPIDA = "O processamento foi interrompido e um reenvio do Telegram o retomou."


def mascarar_start(texto):
    """Troca o código de "/start <código>" por ***: o log não pode guardar um código ainda válido."""
    return START_COM_CODIGO.sub(r"\1 ***", texto)


def _origem(update):
    """Devolve (remetente, mensagem) se for uma pessoa em conversa privada, ou None se não for."""
    callback = update.get("callback_query")
    mensagem = callback.get("message") if callback else update.get("message")
    remetente = (callback or mensagem or {}).get("from")
    chat = (mensagem or {}).get("chat")
    if not remetente or remetente.get("is_bot") or not chat or chat.get("type") != "private":
        return None
    return remetente, mensagem


def _tipo(update):
    if "callback_query" in update:
        return "botao"
    mensagem = update["message"]
    if roteador.tem_arquivo(mensagem):
        return "arquivo"
    if roteador.eh_comando(mensagem):
        return "comando"
    return "texto" if mensagem.get("text") else "outro"


def _texto(update):
    callback = update.get("callback_query")
    if callback:
        return callback.get("data", "")
    return update["message"].get("text") or update["message"].get("caption", "")


def _conteudo(update):
    """Cópia do update sem segredos, porque o texto vai também dentro do JSON."""
    mensagem = update.get("message")
    if mensagem and "text" in mensagem:
        update = {**update, "message": {**mensagem, "text": mascarar_start(mensagem["text"])}}
    return json.loads(mascarar(json.dumps(update, ensure_ascii=False)))


def _retomar(registro):
    """Só o primeiro reenvio retoma: sair de "recebida" impede que outro reenvio passe por aqui."""
    limite = timezone.now() - timedelta(seconds=settings.TELEGRAM_REPROCESSAR_APOS_S)
    return MensagemTelegram.objects.filter(
        pk=registro.pk, situacao=MensagemTelegram.Situacao.RECEBIDA, criado_em__lte=limite,
    ).update(situacao=MensagemTelegram.Situacao.ERRO, erro=INTERROMPIDA) > 0


def _registrar(update, remetente, mensagem, vinculo):
    """Grava a entrada e devolve o registro, ou None se for um reenvio que não deve ser processado."""
    registro, criado = MensagemTelegram.objects.get_or_create(
        update_id=update["update_id"],
        defaults={
            "direcao": MensagemTelegram.Direcao.ENTRADA,
            "tipo": _tipo(update),
            "telegram_id": remetente["id"],
            "chat_id": mensagem["chat"]["id"],
            "mensagem_id": mensagem.get("message_id"),
            "usuario": vinculo.usuario if vinculo else None,
            "texto": mascarar(mascarar_start(_texto(update))),
            # JSON só de quem está conectado
            "conteudo": _conteudo(update) if vinculo else None,
            "situacao": MensagemTelegram.Situacao.RECEBIDA,
        },
    )
    return registro if criado or _retomar(registro) else None


def _tratar_falha(falha, registro, vinculo):
    logger.exception("Falha ao tratar o update %s do Telegram.", registro.update_id)
    registro.situacao = MensagemTelegram.Situacao.ERRO
    registro.erro = mascarar("{}: {}".format(type(falha).__name__, falha))
    registro.save(update_fields=["situacao", "erro"])
    if limites.pode_avisar_erro(registro.telegram_id):
        obter_cliente().enviar(
            registro.chat_id, ERRO_GENERICO, contexto=contexto_do_log(registro.telegram_id, vinculo, "erro"),
        )


def receber(update):
    """
    Trata um update autenticado. Erro no atendimento não sobe: repetir daria o mesmo erro e
    seguraria os updates seguintes. Já uma falha antes de gravar sobe, e o Telegram repete depois.
    """
    origem = _origem(update)
    if origem is None:
        return
    remetente, mensagem = origem
    vinculo = services.vinculo_valido(remetente["id"])

    # A mensagem de um botão é a do bot, por isso arquivo e comando olham só o que a pessoa enviou.
    # A foto de um álbum não conta como arquivo: o álbum inteiro vira uma importação só.
    enviada = update.get("message", {})
    arquivo = roteador.tem_arquivo(enviada) and not enviada.get("media_group_id")
    veredito = limites.verificar(
        remetente["id"], conectado=vinculo is not None, arquivo=arquivo, comando=roteador.eh_comando(enviada),
    )
    if veredito.aviso:
        obter_cliente().enviar(
            mensagem["chat"]["id"], veredito.aviso, contexto=contexto_do_log(remetente["id"], vinculo, "aviso"),
        )
    if not veredito.seguir:
        return

    registro = _registrar(update, remetente, mensagem, vinculo)
    if registro is None:
        return
    try:
        roteador.processar(update, registro)
    except Exception as falha:
        _tratar_falha(falha, registro, vinculo)
