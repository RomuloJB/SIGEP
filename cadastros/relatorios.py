"""
Relatórios gerenciais: os números por trás dos gráficos do painel gerencial.

Tudo sai dos pedidos da empresa ativa que o usuário pode ver (RN02), no período do
filtro. Só pedido APROVADO conta como venda; os demais status entram apenas no
funil de status e na taxa de aprovação. As funções devolvem tipos simples (listas
de rótulos e números) que a view entrega como JSON para o Chart.js.
"""
from decimal import Decimal

from django.db.models import Count, Sum

from .models import OrderStatus, PaymentMethod, Product, ProductOrder

# Abaixo disso o produto aparece no gráfico de estoque crítico
LIMITE_ESTOQUE_BAIXO = 10
TOP_N = 10


def _numero(valor):
    return float(valor or 0)


def _serie(linhas, campo_rotulo, campo_valor, rotulo=lambda r: r):
    """Duas listas paralelas (rótulos e valores) a partir de um values()/annotate()."""
    linhas = list(linhas)
    return {
        "labels": [rotulo(linha[campo_rotulo]) for linha in linhas],
        "valores": [_numero(linha[campo_valor]) for linha in linhas],
    }


def funil_de_status(pedidos):
    """Quantos pedidos há em cada status, na ordem do ciclo de vida do pedido."""
    contagem = {
        linha["status"]: linha["qtd"]
        for linha in pedidos.order_by().values("status").annotate(qtd=Count("id"))
    }
    return {
        "labels": [status.label for status in OrderStatus],
        "chaves": [status.value for status in OrderStatus],
        "valores": [contagem.get(status.value, 0) for status in OrderStatus],
    }


def resumo_de_vendas(pedidos):
    """Indicadores do topo: vendas, ticket médio, taxa de aprovação e pendências."""
    por_status = {
        linha["status"]: linha
        for linha in pedidos.order_by().values("status").annotate(qtd=Count("id"), total=Sum("total_value"))
    }
    aprovados = por_status.get(OrderStatus.APROVADO, {"qtd": 0, "total": 0})
    rejeitados = por_status.get(OrderStatus.REJEITADO, {"qtd": 0})
    pendentes = por_status.get(OrderStatus.PENDENTE, {"qtd": 0, "total": 0})

    qtd = aprovados["qtd"]
    total = aprovados["total"] or Decimal("0")
    decididos = qtd + rejeitados["qtd"]
    return {
        "total_vendido": total,
        "qtd_vendas": qtd,
        "ticket_medio": total / qtd if qtd else Decimal("0"),
        # Dos pedidos que o gerente já decidiu, quantos foram aprovados
        "taxa_aprovacao": (qtd * 100 / decididos) if decididos else None,
        "pendentes_qtd": pendentes["qtd"],
        "pendentes_valor": pendentes["total"] or Decimal("0"),
    }


def vendas_por_forma_de_pagamento(vendas):
    rotulos = dict(PaymentMethod.choices)
    return _serie(
        vendas.order_by().values("payment_method").annotate(total=Sum("total_value")).order_by("-total"),
        "payment_method", "total", rotulo=lambda chave: rotulos.get(chave, chave),
    )


def vendas_por_uf(vendas):
    return _serie(
        vendas.order_by().values("uf").annotate(total=Sum("total_value")).order_by("-total"),
        "uf", "total",
    )


def melhores_clientes(vendas):
    return _serie(
        vendas.order_by().values("client__name").annotate(total=Sum("total_value")).order_by("-total")[:TOP_N],
        "client__name", "total",
    )


def vendas_por_representante(vendas):
    linhas = (
        vendas.order_by()
        .values("created_by__username", "created_by__profile__name")
        .annotate(total=Sum("total_value"))
        .order_by("-total")[:TOP_N]
    )
    linhas = [
        {"nome": linha["created_by__profile__name"] or linha["created_by__username"], "total": linha["total"]}
        for linha in linhas
    ]
    return _serie(linhas, "nome", "total")


def itens_vendidos(vendas):
    return ProductOrder.objects.filter(order__in=vendas.order_by()).exclude(product=None)


def melhores_produtos(itens):
    return _serie(
        itens.values("product__name").annotate(total=Sum("total_value")).order_by("-total")[:TOP_N],
        "product__name", "total",
    )


def descontos(itens):
    """Total de descontos concedidos e quanto isso representa do valor de tabela."""
    soma = itens.aggregate(desconto=Sum("discount"), vendido=Sum("total_value"))
    desconto = soma["desconto"] or Decimal("0")
    bruto = (soma["vendido"] or Decimal("0")) + desconto
    return {"valor": desconto, "percentual": (desconto * 100 / bruto) if bruto else Decimal("0")}


def estoque_critico(empresa):
    """Produtos da empresa com pouco estoque, do menor para o maior."""
    produtos = Product.objects.filter(company=empresa, stock__lte=LIMITE_ESTOQUE_BAIXO).order_by("stock", "name")[:TOP_N]
    return _serie(produtos.values("name", "stock"), "name", "stock")


def produtos_sem_venda(empresa, itens):
    """Quantos produtos cadastrados não venderam nada no período."""
    return Product.objects.filter(company=empresa).exclude(pk__in=itens.values("product_id")).count()


def dados_gerenciais(pedidos, vendas, empresa, ve_todos):
    """Tudo o que o painel gerencial mostra, de uma vez."""
    itens = itens_vendidos(vendas)
    graficos = {
        "status": funil_de_status(pedidos),
        "pagamento": vendas_por_forma_de_pagamento(vendas),
        "uf": vendas_por_uf(vendas),
        "produtos": melhores_produtos(itens),
        "clientes": melhores_clientes(vendas),
        "estoque": estoque_critico(empresa),
    }
    if ve_todos:
        graficos["representantes"] = vendas_por_representante(vendas)
    return {
        "resumo": resumo_de_vendas(pedidos),
        "descontos": descontos(itens),
        "sem_venda": produtos_sem_venda(empresa, itens),
        "graficos": graficos,
    }
