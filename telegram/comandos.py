"""
Comandos do bot. Aqui fica só a conversa: as regras estão nos services e nas consultas que o
site usa. O bot só consulta: nenhum comando muda um pedido.
"""
from functools import wraps
from html import escape

from django.conf import settings
from django.urls import reverse

from . import conversa, entradas, services, telas
from .cliente import botao_link, contexto_do_log, obter_cliente

# A ajuda e o menu do Telegram (setMyCommands) saem desta lista, a mesma que executar() atende:
# assim o menu nunca fica diferente do que o bot entende. Nome sem a barra, como o Telegram pede.
COMANDOS_DO_MENU = (
    ("aprovacoes", "Pedidos aguardando aprovação"),
    ("pedido", "Ver um pedido pelo número. Exemplo: /pedido 128"),
    ("estoque", "Consultar produtos e estoque. Exemplo: /estoque caderno"),
    ("empresa", "Trocar a empresa usada nos comandos"),
    ("ajuda", "O que o bot faz e a lista de comandos"),
    ("cancelar", "Cancelar a pergunta em andamento"),
    ("desconectar", "Desligar este Telegram do seu usuário"),
)

BOAS_VINDAS = "👋 Olá! Eu sou o bot do SIGEP."
SOBRE = "Pelo bot você consulta os pedidos aguardando aprovação, um pedido pelo número e o estoque dos produtos."
COMO_CONECTAR = (
    "Para usar o bot, conecte o seu usuário: entre no site, abra o menu do usuário, "
    "clique em <b>Telegram</b> e depois em <b>Conectar Telegram</b>."
)
AJUDA = "<b>Comandos</b>\n" + "\n".join("/{}: {}".format(nome, descricao) for nome, descricao in COMANDOS_DO_MENU)
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
    if not telas.site_tem_https():
        return None
    return [[botao_link("Abrir o site", settings.SITE_URL + reverse("telegram:conexao"))]]


def _responder(mensagem, vinculo, texto, teclado=None):
    obter_cliente().enviar(
        mensagem["chat"]["id"], texto, teclado=teclado, contexto=contexto_do_log(mensagem["from"]["id"], vinculo),
    )


def _mostrar(mensagem, vinculo, desenhar):
    """Manda a tela. Texto que não deu para entender ou registro que a pessoa não vê viram a resposta."""
    try:
        tela = desenhar()
    except (entradas.EntradaInvalida, telas.Recusa) as erro:
        tela = telas.Tela(escape(str(erro), quote=False))
    _responder(mensagem, vinculo, tela.texto, tela.teclado)


def _so_conectado(comando):
    @wraps(comando)
    def executar_conectado(mensagem, argumento, vinculo):
        if vinculo is None:
            _responder(mensagem, vinculo, COMO_CONECTAR, teclado_do_site())
            return
        comando(mensagem, argumento, vinculo)
    return executar_conectado


# ─── Conexão e ajuda ──────────────────────────────────────────────────────────

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
    _responder(mensagem, vinculo, "{}\n\n{}".format(BOAS_VINDAS, complemento))


def ajuda(mensagem, argumento, vinculo):
    if vinculo:
        _responder(mensagem, vinculo, "{}\n\n{}".format(SOBRE, AJUDA))
    else:
        _responder(mensagem, vinculo, "{}\n\n{}".format(SOBRE, COMO_CONECTAR), teclado_do_site())


def desconectar(mensagem, argumento, vinculo):
    texto = DESCONECTADO if vinculo and services.desconectar(vinculo.usuario) else NAO_CONECTADO
    _responder(mensagem, vinculo, texto)


def cancelar(mensagem, argumento, vinculo):
    texto = CANCELADO if vinculo and conversa.cancelar(vinculo) else NADA_PARA_CANCELAR
    _responder(mensagem, vinculo, texto)


# ─── Consultas do SIGEP ───────────────────────────────────────────────────────

@_so_conectado
def aprovacoes(mensagem, argumento, vinculo):
    _mostrar(mensagem, vinculo, lambda: telas.aprovacoes(vinculo))


@_so_conectado
def pedido(mensagem, argumento, vinculo):
    if argumento:
        _mostrar(mensagem, vinculo, lambda: telas.pedido(vinculo, entradas.interpretar_numero(argumento)))
    elif services.empresa_do_vinculo(vinculo) is None:
        _mostrar(mensagem, vinculo, lambda: telas.empresas(vinculo))
    else:
        conversa.pedir(vinculo, "pedido", mensagem["chat"]["id"])


@_so_conectado
def estoque(mensagem, argumento, vinculo):
    _mostrar(mensagem, vinculo, lambda: telas.estoque(vinculo, entradas.interpretar_termo(argumento) if argumento else ""))


@_so_conectado
def empresa(mensagem, argumento, vinculo):
    _mostrar(mensagem, vinculo, lambda: telas.empresas(vinculo))


COMANDOS = {
    "/start": start,
    "/ajuda": ajuda,
    "/cancelar": cancelar,
    "/desconectar": desconectar,
    "/aprovacoes": aprovacoes,
    "/pedido": pedido,
    "/estoque": estoque,
    "/empresa": empresa,
}


def separar(texto):
    """'/pedido@sigep_bot 128' -> ('/pedido', '128'). Comando para outro bot -> ('', '')."""
    nome, *argumento = texto.split(maxsplit=1) or [""]
    nome, _, bot = nome.partition("@")
    if bot and bot.lower() != settings.TELEGRAM_BOT_USERNAME.lower():
        return "", ""
    return nome.lower(), argumento[0].strip() if argumento else ""


def executar(texto, mensagem, vinculo, registro):
    """Roda o comando do texto. Devolve False se não for um comando conhecido."""
    nome, argumento = separar(texto)
    comando = COMANDOS.get(nome)
    if comando is None:
        return False
    comando(mensagem, argumento, vinculo)
    return True
