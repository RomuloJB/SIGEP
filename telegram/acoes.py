"""Botões do bot. O callback_data tem a forma "acao:argumento", como em "ok:45"."""
from .cliente import contexto_do_log, obter_cliente

BOTAO_SEM_USO = "Este botão não vale mais."

# ação do callback_data -> função(callback, argumento, vinculo). Cada funcionalidade registra as suas aqui.
ACOES = {}


def despachar(callback, vinculo):
    nome, _, argumento = callback.get("data", "").partition(":")
    acao = ACOES.get(nome)
    if vinculo is None or acao is None:
        obter_cliente().responder_botao(
            callback["id"], BOTAO_SEM_USO, contexto=contexto_do_log(callback["from"]["id"], vinculo, "botao"),
        )
        return
    acao(callback, argumento, vinculo)
