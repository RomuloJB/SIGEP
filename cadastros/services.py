"""
Regras de gravação do app cadastros. A tela de pedido do site e a importação de documentos
chamam estas funções: a mesma regra nos dois lugares.

O ciclo de status e o estoque ficam em pedidos.py; as consultas de leitura, em consultas.py.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.core.mail import send_mail
from django.template.loader import render_to_string

from . import pedidos
from .models import OrderStatus, Product, ProductOrder

logger = logging.getLogger(__name__)


def conferir_itens(empresa, linhas, enviando):
    """
    Confere os itens do pedido: `linhas` é uma lista de (produto_id, quantidade, desconto) em
    texto, como chegam do formulário. Devolve (itens, erros), com itens no formato
    (produto, quantidade, desconto, total do item).

    Trava os produtos com select_for_update: chame dentro de transaction.atomic. O estoque só é
    conferido ao enviar: o rascunho não reserva nada, e a conferência acontece quando ele passa
    para Pendente.
    """
    linhas = list(linhas)
    # Um SELECT ... FOR UPDATE só para todos os produtos do pedido (em vez de um por item)
    ids_validos = {int(pid) for pid, _, _ in linhas if pid.isdigit()}
    produtos = Product.objects.select_for_update().filter(pk__in=ids_validos, company=empresa).in_bulk()

    items = []
    errors = []
    vistos = set()

    for pid, qty_str, disc_str in linhas:
        product = produtos.get(int(pid)) if pid.isdigit() else None
        if product is None:
            errors.append(f"Produto inválido (id={pid}).")
            continue

        if product.pk in vistos:
            errors.append(f"O produto '{product.name}' aparece mais de uma vez.")
            continue
        vistos.add(product.pk)

        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f"Quantidade inválida para o produto '{product.name}'.")
            continue

        try:
            discount = Decimal(disc_str) if disc_str else Decimal("0")
            if discount < 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            errors.append(f"Desconto inválido para o produto '{product.name}'.")
            continue

        if enviando and (product.stock or 0) < qty:
            errors.append(
                f"Estoque insuficiente para '{product.name}': "
                f"disponível {product.stock}, solicitado {qty}."
            )
            continue

        subtotal = product.unit_value * qty
        if discount > subtotal:
            errors.append(f"Desconto maior que o valor do item '{product.name}'.")
            continue

        items.append((product, qty, discount, subtotal - discount))

    return items, errors


def salvar_pedido(pedido, itens, enviar=False):
    """
    Grava o pedido (novo ou rascunho editado) com os itens que conferir_itens devolveu, na mesma
    transação. O cabeçalho (empresa, cliente, autor, pagamento...) já vem preenchido em `pedido`.

    O total sai dos itens, o pedido fica Em digitação e os itens são regravados (o rascunho não
    tem estoque baixado). Com enviar, ele passa para Pendente e o estoque é baixado (RN05/RN08):
    pode levantar pedidos.EstoqueInsuficiente, e então nada é gravado.
    """
    pedido.total_value = sum(line_total for _, _, _, line_total in itens)
    pedido.status = OrderStatus.EM_DIGITACAO
    pedido.save()

    pedido.product_orders.all().delete()
    ProductOrder.objects.bulk_create([
        ProductOrder(
            order=pedido,
            product=product,
            quantity=qty,
            unit_value=product.unit_value or 0,
            discount=discount,
            total_value=line_total,
        )
        for product, qty, discount, line_total in itens
    ])

    if enviar:
        # O estoque já foi conferido com os produtos travados: aqui ele é baixado
        pedidos.alterar_status(pedido, OrderStatus.PENDENTE)
    return pedido


def criar_cliente(form, empresa, usuario):
    """Grava o cliente de um ClientForm já validado, na empresa e com o autor, como a tela de cadastro."""
    cliente = form.save(commit=False)
    cliente.company = empresa
    cliente.created_by = usuario
    cliente.save()
    return cliente


def notificar_gerentes_pedido_enviado(pedido, remetente, url):
    """
    RF07: avisa por e-mail os gerentes da empresa que um pedido aguarda aprovação. `url` é o
    endereço completo do pedido. Chame depois do commit: se o pedido falhar, ninguém é avisado.
    """
    # Quem enviou não recebe o próprio aviso
    destinatarios = list(
        pedido.company.manager.exclude(pk=remetente.pk)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not destinatarios:
        return

    contexto = {
        "pedido": pedido,
        "itens": pedido.product_orders.select_related("product"),
        "url": url,
    }
    assunto = "Pedido #{} aguardando aprovação — {}".format(pedido.pk, pedido.client.name)
    corpo = render_to_string("cadastros/email/novo_pedido.txt", contexto)
    try:
        send_mail(assunto, corpo, None, destinatarios)
    except Exception:
        # O pedido já foi gravado: falha no SMTP fica no log, não vira erro 500
        logger.exception("Falha ao enviar o e-mail do pedido #%s aos gerentes", pedido.pk)
