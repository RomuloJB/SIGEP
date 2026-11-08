"""
Fila de tarefas em segundo plano, para o que não pode rodar dentro da requisição (ler um
arquivo com a IA leva segundos).

    @tarefa("importacao.ler")
    def ler(importacao_id): ...

    enfileirar("importacao.ler", ao_recusar=lambda: ..., importacao_id=10)

A tarefa só sai depois do commit (transaction.on_commit). TAREFAS_BACKEND, no .env:
- "imediata" (padrão, desenvolvimento): roda logo depois do commit, no mesmo processo;
- "cloud_tasks" (produção): cria uma tarefa no Cloud Tasks, que chama
  POST /importacao/tarefas/<nome>/ com o cabeçalho X-Tarefas-Segredo.
Os parâmetros precisam caber em JSON. Se a fila recusar, ao_recusar() é chamada.
"""
import base64
import json
import logging
import os

from django.conf import settings
from django.db import transaction
from django.urls import reverse

logger = logging.getLogger(__name__)

TAREFAS = {}  # nome -> função
CABECALHO_SEGREDO = "X-Tarefas-Segredo"
URL_CLOUD_TASKS = "https://cloudtasks.googleapis.com/v2/{fila}/tasks"
ESCOPO_GOOGLE = "https://www.googleapis.com/auth/cloud-platform"


class FilaRecusou(Exception):
    """A tarefa não pôde ser agendada."""


def tarefa(nome):
    """Decorador: registra a função como tarefa."""
    def registrar(funcao):
        TAREFAS[nome] = funcao
        return funcao
    return registrar


def enfileirar(nome, ao_recusar=None, **params):
    """Agenda a tarefa para depois do commit da transação atual."""
    if nome not in TAREFAS:
        raise ValueError("Tarefa desconhecida: {!r}".format(nome))
    transaction.on_commit(lambda: _despachar(nome, params, ao_recusar))


def executar(nome, params):
    TAREFAS[nome](**params)


def _despachar(nome, params, ao_recusar):
    try:
        if settings.TAREFAS_BACKEND == "imediata":
            executar(nome, params)
        elif settings.TAREFAS_BACKEND == "cloud_tasks":
            _criar_no_cloud_tasks(nome, params)
        else:
            raise FilaRecusou("TAREFAS_BACKEND desconhecido: {!r}".format(settings.TAREFAS_BACKEND))
    except Exception:
        logger.exception("A tarefa %s não pôde ser executada ou agendada.", nome)
        if ao_recusar is not None:
            try:
                ao_recusar()
            except Exception:
                logger.exception("Falha ao tratar a recusa da tarefa %s.", nome)


def _criar_no_cloud_tasks(nome, params):
    # Só a produção usa: o google-auth pega a conta de serviço do App Engine sozinho
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    segredo = os.getenv("TAREFAS_SEGREDO", "")
    if not settings.TAREFAS_FILA or not segredo:
        raise FilaRecusou("Configure TAREFAS_FILA e TAREFAS_SEGREDO no .env para usar o Cloud Tasks.")
    corpo = {"task": {"appEngineHttpRequest": {
        "httpMethod": "POST",
        "relativeUri": reverse("importacao:tarefa", args=[nome]),
        "headers": {"Content-Type": "application/json", CABECALHO_SEGREDO: segredo},
        "body": base64.b64encode(json.dumps(params).encode("utf-8")).decode("ascii"),
    }}}
    credenciais, _ = google.auth.default(scopes=[ESCOPO_GOOGLE])
    resposta = AuthorizedSession(credenciais).post(URL_CLOUD_TASKS.format(fila=settings.TAREFAS_FILA), json=corpo, timeout=10)
    if resposta.status_code >= 300:
        raise FilaRecusou("O Cloud Tasks respondeu {}: {}".format(resposta.status_code, resposta.text[:300]))
