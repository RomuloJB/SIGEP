"""Comandos do bot. Aqui fica só a conversa: as regras estão no services.py, o mesmo que o site usa."""
from html import escape

from django.conf import settings
from django.urls import reverse

from . import conversa, services
from .cliente import botao_link, contexto_do_log, obter_cliente

BOAS_VINDAS = "👋 Olá! Eu sou o bot do SIGEP."
COMO_CONECTAR = (
    "Para usar o bot, conecte o seu usuário: entre no site, abra o menu do usuário, "
    "clique em <b>Telegram</b> e depois em <b>Conectar Telegram</b>."
)
AJUDA = (
    "<b>Comandos</b>\n"
    "/start: mostra esta mensagem\n"
    "/cancelar: cancela a pergunta em andamento\n"
    "/desconectar: desliga este Telegram do seu usuário"
)
CODIGO_INVALIDO = "Este código não vale mais. Gere outro no site."
DESCONECTADO = "Pronto, este Telegram foi desconectado do seu usuário."
NAO_CONECTADO = "Este Telegram não está conectado a nenhum usuário."
CANCELADO = "Pronto, cancelei a pergunta."
NADA_PARA_CANCELAR = "Não há nada para cancelar."


def primeiro_nome(usuario):
    """O cadastro guarda o nome no perfil; usuários do createsuperuser não têm perfil."""
    perfil = getattr(usuario, "profile", None)
    nome = (perfil.name if perfil else "") or usuario.first_name or usuario.get_username()
    return nome.split()[0]


def _nome_no_telegram(remetente):
    return " ".join(filter(None, [remetente.get("first_name"), remetente.get("last_name")]))


def teclado_do_site():
    """Botão para a tela Telegram. Só com https: o Telegram recusa o endereço local do desenvolvimento."""
    if not settings.SITE_URL.startswith("https://"):
        return None
    return [[botao_link("Abrir o site", settings.SITE_URL + reverse("telegram:conexao"))]]


def _start_com_codigo(mensagem, codigo, vinculo):
    remetente = mensagem["from"]
    telegram_id = remetente["id"]
    chat_id = mensagem["chat"]["id"]
    novo = services.conectar(
        codigo, telegram_id, chat_id, username=remetente.get("username", ""), nome=_nome_no_telegram(remetente),
    )
    if novo is None:
        obter_cliente().enviar(
            chat_id, CODIGO_INVALIDO, teclado=teclado_do_site(), contexto=contexto_do_log(telegram_id, vinculo),
        )
        return
    texto = "✅ Conectado como {}\n\n{}".format(escape(primeiro_nome(novo.usuario), quote=False), AJUDA)
    obter_cliente().enviar(chat_id, texto, contexto=contexto_do_log(telegram_id, novo))


def start(mensagem, argumento, vinculo):
    if argumento:
        _start_com_codigo(mensagem, argumento, vinculo)
        return
    complemento = AJUDA if vinculo else COMO_CONECTAR
    obter_cliente().enviar(
        mensagem["chat"]["id"], "{}\n\n{}".format(BOAS_VINDAS, complemento),
        contexto=contexto_do_log(mensagem["from"]["id"], vinculo),
    )


def desconectar(mensagem, argumento, vinculo):
    texto = DESCONECTADO if vinculo and services.desconectar(vinculo.usuario) else NAO_CONECTADO
    obter_cliente().enviar(mensagem["chat"]["id"], texto, contexto=contexto_do_log(mensagem["from"]["id"], vinculo))


def cancelar(mensagem, argumento, vinculo):
    texto = CANCELADO if vinculo and conversa.cancelar(vinculo) else NADA_PARA_CANCELAR
    obter_cliente().enviar(mensagem["chat"]["id"], texto, contexto=contexto_do_log(mensagem["from"]["id"], vinculo))


COMANDOS = {"/start": start, "/cancelar": cancelar, "/desconectar": desconectar}


def executar(mensagem, vinculo):
    """Roda o comando da mensagem. Devolve False se o texto não for um comando conhecido."""
    nome, *argumento = mensagem.get("text", "").split(maxsplit=1) or [""]
    comando = COMANDOS.get(nome.split("@")[0].lower())
    if comando is None:
        return False
    comando(mensagem, argumento[0].strip() if argumento else "", vinculo)
    return True
