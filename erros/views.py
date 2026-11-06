"""
Páginas de erro do SIGEP (400, 403, 404, 500 e falha de CSRF).

Com DEBUG=False (App Engine) o Django usa estas views no lugar da página técnica.
Elas renderizam sem `request`, de propósito: assim não executam os context
processors (que consultam o banco) nem dependem de sessão ou de usuário logado,
e a página continua abrindo mesmo quando o erro foi no banco ou na sessão.
Configuradas em naes2026/urls.py (handler400/403/404/500) e em settings.py
(CSRF_FAILURE_VIEW).
"""

from django.http import HttpResponse
from django.template.loader import render_to_string

PAGINAS = {
    400: {
        "titulo": "Requisição inválida",
        "mensagem": "O servidor não entendeu o pedido. Volte e tente novamente.",
        "icone": "fa-circle-exclamation",
    },
    403: {
        "titulo": "Acesso negado",
        "mensagem": "Você não tem permissão para acessar esta página.",
        "icone": "fa-lock",
    },
    404: {
        "titulo": "Página não encontrada",
        "mensagem": "O endereço que você acessou não existe ou foi removido.",
        "icone": "fa-magnifying-glass",
    },
    500: {
        "titulo": "Erro no servidor",
        "mensagem": "Algo deu errado do nosso lado. Tente novamente em instantes.",
        "icone": "fa-triangle-exclamation",
    },
}


def _resposta(status, contexto=None):
    contexto = contexto or dict(PAGINAS[status], codigo=status)
    return HttpResponse(render_to_string("erros/erro.html", contexto), status=status)


def erro_400(request, exception=None):
    return _resposta(400)


def erro_403(request, exception=None):
    return _resposta(403)


def erro_404(request, exception=None):
    return _resposta(404)


def erro_500(request):
    return _resposta(500)


def erro_csrf(request, reason=""):
    """Formulário vencido ou enviado de outra origem (CSRF_FAILURE_VIEW)."""
    return _resposta(403, {
        "codigo": 403,
        "titulo": "Sessão expirada",
        "mensagem": "O formulário expirou ou veio de outra origem. Volte, recarregue a página e envie de novo.",
        "icone": "fa-clock",
    })
