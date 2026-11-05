from django import template
from django.urls import reverse

register = template.Library()


def item(rotulo, rota, icone, ativo_em=None):
    """
    Opção do menu. `icone` é o id em static/assets/icons/sidebar.svg. `ativo_em` são
    os começos de nome de rota que marcam a opção como atual; assim "client-" cobre
    a listagem e também as telas de criar, editar e detalhe.
    """
    return {"rotulo": rotulo, "rota": rota, "icone": icone, "ativo_em": ativo_em or (rota,)}


INICIO = ("Início", [item("Dashboard", "index", "layout-dashboard")])
EMPRESAS = item("Empresas", "company-list", "building-2", ("company-",))
PAGINAS = [
    item("Clientes", "client-list", "users", ("client-",)),
    item("Produtos", "product-list", "package", ("product-",)),
    item("Pedidos", "order-list", "shopping-bag", ("order-", "productorder-")),
]
ADICIONAIS = ("Adicionais", [
    item("Relatórios", "sales-report", "chart-no-axes-combined"),
    item("Sobre", "about", "info"),
    item("Meu consumo de IA", "ia:meu-consumo", "bot"),
])
ADMINISTRACAO = ("Administração", [
    item("Gerenciar Usuários", "user-list", "users-round", ("user-",)),
    item("Requisições de IA", "ia:requisicao-list", "list-checks", ("ia:requisicao-",)),
    item("Configuração da IA", "ia:configuracao", "settings"),
    item("IA por usuário", "ia:usuario-list", "user-cog", ("ia:usuario-",)),
])
VISITANTE = ("Acesso", [
    item("Entrar", "login", "log-in"),
    item("Sobre", "about", "info"),
])


def grupos_do_usuario(user, is_manager):
    if not user.is_authenticated:
        return [VISITANTE]
    paginas = [EMPRESAS, *PAGINAS] if is_manager else PAGINAS
    grupos = [INICIO, ("Páginas", paginas), ADICIONAIS]
    if user.is_superuser:
        grupos.append(ADMINISTRACAO)
    return grupos


@register.simple_tag(takes_context=True)
def menu_lateral(context):
    """Grupos e opções do menu para o usuário logado, com a página atual marcada."""
    request = context["request"]
    rota_atual = request.resolver_match.view_name if request.resolver_match else ""
    return [
        {
            "titulo": titulo,
            "itens": [
                {**opcao, "url": reverse(opcao["rota"]), "ativo": rota_atual.startswith(opcao["ativo_em"])}
                for opcao in opcoes
            ],
        }
        for titulo, opcoes in grupos_do_usuario(request.user, context.get("is_manager", False))
    ]


@register.filter
def iniciais(nome):
    """Até duas letras para o avatar: primeira e última palavra do nome."""
    partes = str(nome).split()
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()
