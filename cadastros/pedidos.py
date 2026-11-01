"""
Ciclo de vida do pedido: quem pode mudar o status e o que acontece com o estoque.

O estoque dos itens fica baixado enquanto o pedido está Pendente ou Aprovado (RN08)
e volta quando ele sai desses status para Em digitação, Rejeitado ou Cancelado (RN09).
Assim o estoque nunca é baixado duas vezes nem fica preso em pedido que não vai sair.
"""
from collections import Counter

from django.db.models import F

from .models import OrderStatus, Product

ESTOQUE_BAIXADO = {OrderStatus.PENDENTE, OrderStatus.APROVADO}

# RN03/RN05: o representante só envia o rascunho e cancela antes da aprovação.
# O gerente muda para qualquer status, e só ele aprova ou rejeita.
TRANSICOES_REPRESENTANTE = {
    OrderStatus.EM_DIGITACAO: [OrderStatus.PENDENTE, OrderStatus.CANCELADO],
    OrderStatus.PENDENTE: [OrderStatus.CANCELADO],
}

# Botão de cada status de destino na tela do pedido: rótulo, classe, classe do
# botão de confirmação no Bootbox e ícone
ACOES = {
    OrderStatus.EM_DIGITACAO: ("Voltar para digitação", "btn-outline-secondary", "btn-primary", "fa-pen"),
    OrderStatus.PENDENTE: ("Enviar para aprovação", "btn-success", "btn-success", "fa-paper-plane"),
    OrderStatus.APROVADO: ("Aprovar", "btn-success", "btn-success", "fa-check"),
    OrderStatus.REJEITADO: ("Rejeitar", "btn-outline-danger", "btn-danger", "fa-xmark"),
    OrderStatus.CANCELADO: ("Cancelar pedido", "btn-outline-danger", "btn-danger", "fa-ban"),
}


class EstoqueInsuficiente(Exception):
    def __init__(self, mensagens):
        super().__init__(" ".join(mensagens))
        self.mensagens = mensagens


def status_permitidos(pedido, gerente):
    if gerente:
        return [status for status in OrderStatus.values if status != pedido.status]
    return TRANSICOES_REPRESENTANTE.get(pedido.status, [])


def quantidades_por_produto(pedido):
    quantidades = Counter()
    for product_id, quantity in pedido.product_orders.exclude(product=None).values_list("product_id", "quantity"):
        quantidades[product_id] += quantity
    return quantidades


def baixar_estoque(pedido):
    quantidades = quantidades_por_produto(pedido)
    produtos = Product.objects.select_for_update().in_bulk(list(quantidades))
    erros = [
        "Estoque insuficiente para '{}': disponível {}, solicitado {}.".format(produto.name, produto.stock, quantidades[pk])
        for pk, produto in sorted(produtos.items(), key=lambda par: par[1].name)
        if produto.stock < quantidades[pk]
    ]
    if erros:
        raise EstoqueInsuficiente(erros)
    for pk, quantidade in quantidades.items():
        Product.objects.filter(pk=pk).update(stock=F("stock") - quantidade)


def devolver_estoque(pedido):
    for pk, quantidade in quantidades_por_produto(pedido).items():
        Product.objects.filter(pk=pk).update(stock=F("stock") + quantidade)


def alterar_status(pedido, novo):
    """
    Muda o status e acerta o estoque. Chamar dentro de transaction.atomic, com o
    pedido travado por select_for_update. Sem estoque para enviar ou aprovar, levanta
    EstoqueInsuficiente e nada é gravado.
    """
    baixado_antes = pedido.status in ESTOQUE_BAIXADO
    baixado_depois = novo in ESTOQUE_BAIXADO
    if baixado_depois and not baixado_antes:
        baixar_estoque(pedido)
    elif baixado_antes and not baixado_depois:
        devolver_estoque(pedido)
    pedido.status = novo
    pedido.save(update_fields=["status", "updated_at"])


def mensagem_confirmacao(pedido, novo, gerente):
    partes = ['Mudar o pedido nº {} de "{}" para "{}"?'.format(
        pedido.pk, pedido.get_status_display(), OrderStatus(novo).label,
    )]
    if novo in ESTOQUE_BAIXADO and pedido.status not in ESTOQUE_BAIXADO:
        partes.append("O estoque dos itens será baixado.")
    elif pedido.status in ESTOQUE_BAIXADO and novo not in ESTOQUE_BAIXADO:
        partes.append("O estoque dos itens será devolvido.")
    if novo == OrderStatus.PENDENTE:
        partes.append("Os gerentes serão avisados por e-mail.")
    if novo == OrderStatus.CANCELADO and not gerente:
        partes.append("Depois disso, só um gerente pode reabrir o pedido.")
    return " ".join(partes)


def acoes_disponiveis(pedido, gerente):
    acoes = []
    for status in status_permitidos(pedido, gerente):
        rotulo, classe, classe_confirmar, icone = ACOES[status]
        if status == OrderStatus.PENDENTE and pedido.status != OrderStatus.EM_DIGITACAO:
            rotulo = "Voltar para pendente"
        acoes.append({
            "status": status,
            "rotulo": rotulo,
            "classe": classe,
            "classe_confirmar": classe_confirmar,
            "icone": icone,
            "mensagem": mensagem_confirmacao(pedido, status, gerente),
        })
    return acoes
