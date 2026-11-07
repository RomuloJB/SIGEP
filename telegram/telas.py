"""
Telas do bot: o texto e os botões de cada resposta. Os dados vêm das consultas do site
(cadastros/consultas.py), sempre na empresa do vínculo e só com o que o usuário pode ver.
Todo texto do banco passa por escape(), porque as mensagens usam parse_mode HTML.
"""
import re
from dataclasses import dataclass
from html import escape
from math import ceil
from urllib.parse import quote

from django.conf import settings
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format

from cadastros import consultas
from cadastros.masks import format_cpf_cnpj
from cadastros.models import OrderStatus, Product

from . import services
from .cliente import botao, botao_link

POR_PAGINA = 8
ITENS_NO_CARTAO = 10
TERMO_NO_BOTAO_BYTES = 40  # cabe em "pr:<id>:<página>:<termo>", dentro dos 64 bytes do callback_data

SEM_EMPRESA = "Seu usuário não está em nenhuma empresa. Fale com o administrador do SIGEP."


@dataclass(frozen=True)
class Tela:
    texto: str
    teclado: list | None = None


@dataclass(frozen=True)
class Pagina:
    itens: list
    teclado: list
    numero: int
    total_paginas: int
    total: int


class Recusa(Exception):
    """O pedido da pessoa não pode ser atendido. A mensagem é texto puro, mostrada a ela."""


def reais(valor):
    return "R$ " + number_format(valor, 2, force_grouping=True)


def data_curta(momento):
    return timezone.localtime(momento).strftime("%d/%m/%Y")


def nome_de(usuario):
    perfil = getattr(usuario, "profile", None)
    return (perfil.name if perfil else "") or usuario.get_username()


def cortar_bytes(texto, limite):
    """Corta o texto para caber em `limite` bytes de UTF-8 sem partir um caractere."""
    return texto.encode("utf-8")[:limite].decode("utf-8", "ignore")


def site_tem_https():
    # O Telegram recusa botão com endereço local, como o SITE_URL de desenvolvimento
    return settings.SITE_URL.startswith("https://")


def botao_no_site(empresa, caminho):
    """
    "Abrir no site", ou None sem https. Passa por activate-company porque a empresa da sessão
    no navegador pode não ser a do bot, e aí a página daria 404.
    """
    if not site_tem_https():
        return None
    url = "{}{}?next={}".format(settings.SITE_URL, reverse("activate-company", args=[empresa.pk]), quote(caminho))
    return botao_link("🌐 Abrir no site", url)


def lista_paginada(queryset, pagina, rotulo, opcao, navegar, voltar=None):
    """
    Um botão por item do queryset, POR_PAGINA por página, com Anterior/Próxima e Voltar.
    rotulo(item) é o texto do botão; opcao(item, página) e navegar(página) dão o callback_data.
    """
    total = queryset.count()
    total_paginas = max(1, ceil(total / POR_PAGINA))
    numero = min(max(1, pagina), total_paginas)
    itens = list(queryset[(numero - 1) * POR_PAGINA:numero * POR_PAGINA])

    teclado = [[botao(rotulo(item), opcao(item, numero))] for item in itens]
    navegacao = []
    if numero > 1:
        navegacao.append(botao("◀️ Anterior", navegar(numero - 1)))
    if numero < total_paginas:
        navegacao.append(botao("Próxima ▶️", navegar(numero + 1)))
    if navegacao:
        teclado.append(navegacao)
    if voltar:
        teclado.append([botao("⬅️ Voltar", voltar)])
    return Pagina(itens, teclado, numero, total_paginas, total)


def _rodape(pagina):
    return "\nPágina {} de {}".format(pagina.numero, pagina.total_paginas) if pagina.total_paginas > 1 else ""


# ─── Empresa ──────────────────────────────────────────────────────────────────

def empresas(vinculo, pagina=1):
    """Escolha da empresa do bot. Com uma empresa só, não há o que escolher."""
    atual = services.empresa_do_vinculo(vinculo)
    opcoes = lista_paginada(
        consultas.empresas_do_usuario(vinculo.usuario).order_by("name"), pagina,
        rotulo=lambda empresa: ("✅ " if atual and empresa.pk == atual.pk else "") + empresa.display_name,
        opcao=lambda empresa, _: "em:{}".format(empresa.pk),
        navegar=lambda numero: "ep:{}".format(numero),
    )
    if opcoes.total == 0:
        return Tela(SEM_EMPRESA)
    if opcoes.total == 1:
        return Tela("🏢 Você está só na empresa <b>{}</b>, e ela é usada em todos os comandos.".format(
            escape(atual.display_name)))
    texto = "🏢 <b>Escolha a empresa</b> usada nos comandos do bot."
    if atual:
        texto += "\nAgora: <b>{}</b>".format(escape(atual.display_name))
    return Tela(texto + _rodape(opcoes), opcoes.teclado)


def empresa_escolhida(empresa):
    return Tela(
        "✅ Pronto! Agora os comandos usam a empresa <b>{}</b>.\n\n"
        "Mande o comando de novo: /aprovacoes, /pedido ou /estoque.".format(escape(empresa.display_name))
    )


# ─── Pedidos ──────────────────────────────────────────────────────────────────

def aprovacoes(vinculo, pagina=1):
    """Pedidos pendentes que o usuário pode ver: o gerente vê os da empresa; o representante, os seus."""
    empresa = services.empresa_do_vinculo(vinculo)
    if empresa is None:
        return empresas(vinculo)
    gerente = consultas.ve_todos_os_pedidos(vinculo.usuario, empresa)
    pendentes = (
        consultas.pedidos_visiveis(vinculo.usuario, empresa, gerente)
        .filter(status=OrderStatus.PENDENTE).select_related("client").order_by("-id")
    )
    lista = lista_paginada(
        pendentes, pagina,
        rotulo=lambda pedido: "#{} · {}".format(pedido.pk, pedido.client.name),
        opcao=lambda pedido, numero: "p:{}:{}".format(pedido.pk, numero),
        navegar=lambda numero: "ap:{}".format(numero),
    )
    titulo = "Aguardando aprovação" if gerente else "Seus pedidos aguardando aprovação"
    texto = "⏳ <b>{}</b> · {}".format(titulo, escape(empresa.display_name))
    if not lista.total:
        return Tela(texto + "\n\nNenhum pedido aguardando aprovação.")

    soma = pendentes.aggregate(soma=Sum("total_value"))["soma"]
    linhas = [
        "#{} · {} · {} · {}".format(pedido.pk, escape(pedido.client.name), reais(pedido.total_value), data_curta(pedido.created_at))
        for pedido in lista.itens
    ]
    texto += "\n{} pedido{} · {}{}\n\n{}\n\nToque em um pedido para ver os detalhes.".format(
        lista.total, "" if lista.total == 1 else "s", reais(soma), _rodape(lista), "\n".join(linhas),
    )
    return Tela(texto, lista.teclado)


def _forma_de_pagamento(pedido):
    # Os rótulos do site são numerados ("3 - Boleto(30)"); no bot fica só o nome
    forma = re.sub(r"^\d+ - ", "", pedido.get_payment_method_display())
    if pedido.pago_em_boleto and pedido.installments > 1:
        forma += " em {}x".format(pedido.installments)
    return forma


def pedido(vinculo, numero, pagina_da_lista=0):
    """Cartão do pedido, só para quem pode vê-lo. Com pagina_da_lista, tem Voltar para /aprovacoes."""
    empresa = services.empresa_do_vinculo(vinculo)
    if empresa is None:
        return empresas(vinculo)
    pedido = (
        consultas.pedidos_visiveis(vinculo.usuario, empresa)
        .select_related("client", "created_by__profile").filter(pk=numero).first()
    )
    if pedido is None:
        raise Recusa("Não encontrei o pedido nº {} entre os que você pode ver em {}.".format(numero, empresa.display_name))

    itens = list(pedido.product_orders.select_related("product").order_by("id"))
    linhas = [
        "🧾 <b>Pedido nº {}</b> · {}".format(pedido.pk, pedido.get_status_display()),
        "🏢 {}".format(escape(empresa.display_name)),
        "Cliente: {} ({})".format(escape(pedido.client.name), format_cpf_cnpj(pedido.client.cnpj_cpf)),
        "Criado por: {} em {}".format(escape(nome_de(pedido.created_by)), data_curta(pedido.created_at)),
        "Pagamento: {}".format(escape(_forma_de_pagamento(pedido))),
        "",
        "Itens ({}):".format(len(itens)),
    ]
    for item in itens[:ITENS_NO_CARTAO]:
        produto = escape(item.product.name) if item.product else "(produto excluído)"
        linhas.append("• {} × {} = {}".format(item.quantity, produto, reais(item.total_value)))
    if len(itens) > ITENS_NO_CARTAO:
        linhas.append("… e mais {} itens".format(len(itens) - ITENS_NO_CARTAO))
    linhas.append("\nTotal: <b>{}</b>".format(reais(pedido.total_value)))

    teclado = []
    no_site = botao_no_site(empresa, reverse("order-detail", args=[pedido.pk]))
    if no_site:
        teclado.append([no_site])
    if pagina_da_lista:
        teclado.append([botao("⬅️ Voltar", "ap:{}".format(pagina_da_lista))])
    return Tela("\n".join(linhas), teclado or None)


# ─── Estoque ──────────────────────────────────────────────────────────────────

def estoque(vinculo, termo="", pagina=1):
    """Busca de produto pelo nome ou SKU; sem termo, os produtos com estoque baixo."""
    empresa = services.empresa_do_vinculo(vinculo)
    if empresa is None:
        return empresas(vinculo)
    if termo:
        produtos = consultas.buscar_produtos(empresa, termo)
        titulo = '📦 <b>Produtos com "{}"</b>'.format(escape(termo))
        vazio = "Nenhum produto encontrado."
    else:
        produtos = consultas.produtos_com_estoque_baixo(empresa)
        titulo = "⚠️ <b>Estoque baixo</b> (até {} unidades)".format(consultas.LIMITE_ESTOQUE_BAIXO)
        vazio = "Nenhum produto com estoque baixo. 👍"

    no_botao = cortar_bytes(termo, TERMO_NO_BOTAO_BYTES)
    lista = lista_paginada(
        produtos, pagina,
        rotulo=lambda produto: "{} · {}".format(produto.sku, produto.name),
        opcao=lambda produto, numero: "pr:{}:{}:{}".format(produto.pk, numero, no_botao),
        navegar=lambda numero: "es:{}:{}".format(numero, no_botao),
    )
    texto = "{} · {}".format(titulo, escape(empresa.display_name))
    if lista.total:
        linhas = [
            "<code>{}</code> · {} · {} {}{} · {}".format(
                escape(produto.sku), escape(produto.name), produto.stock, produto.measure_unit,
                " ⚠️" if produto.stock <= consultas.LIMITE_ESTOQUE_BAIXO else "", reais(produto.unit_value),
            )
            for produto in lista.itens
        ]
        texto += "\n{} produto{}{}\n\n{}".format(
            lista.total, "" if lista.total == 1 else "s", _rodape(lista), "\n".join(linhas),
        )
    else:
        texto += "\n\n" + vazio
    return Tela(texto, lista.teclado + [[botao("🔎 Buscar produto", "bp")]])


def produto(vinculo, produto_id, pagina=1, termo=""):
    """Cartão do produto, com Voltar para a lista de onde veio."""
    empresa = services.empresa_do_vinculo(vinculo)
    if empresa is None:
        return empresas(vinculo)
    produto = Product.objects.filter(company=empresa, pk=produto_id).first()
    if produto is None:
        raise Recusa("Este produto não está disponível em {}.".format(empresa.display_name))

    baixo = " ⚠️ estoque baixo" if produto.stock <= consultas.LIMITE_ESTOQUE_BAIXO else ""
    linhas = [
        "📦 <b>{}</b>".format(escape(produto.name)),
        "🏢 {}".format(escape(empresa.display_name)),
        "SKU: <code>{}</code>".format(escape(produto.sku)),
        "Estoque: {} · {}{}".format(produto.stock, escape(produto.get_measure_unit_display()), baixo),
        "Valor unitário: {}".format(reais(produto.unit_value)),
    ]
    if produto.color:
        linhas.append("Cor: {}".format(escape(produto.color)))
    if produto.description:
        linhas.append("Descrição: {}".format(escape(produto.description)))

    teclado = []
    no_site = botao_no_site(empresa, reverse("product-detail", args=[produto.pk]))
    if no_site:
        teclado.append([no_site])
    teclado.append([botao("⬅️ Voltar", "es:{}:{}".format(pagina, cortar_bytes(termo, TERMO_NO_BOTAO_BYTES)))])
    return Tela("\n".join(linhas), teclado)
