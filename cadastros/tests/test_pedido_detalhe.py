from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order, OrderStatus, Product, ProductOrder

from .base import CadastrosTestCase


class DetalheDoPedidoTests(CadastrosTestCase):
    """
    CB08 (TC-21): OrderDetail.get_context_data carrega os itens do pedido em
    product_orders e soma os totais deles em product_orders_total.
    """

    def setUp(self):
        super().setUp()
        outro_produto = Product.objects.create(
            name="Produto Dois", sku="PD-2", unit_value=Decimal("20.00"), stock=10,
            company=self.empresa, created_by=self.gerente,
        )
        self.pedido = Order.objects.create(
            company=self.empresa, client=self.cliente, uf="PR", status=OrderStatus.APROVADO,
            total_value=Decimal("30.00"), created_by=self.gerente,
        )
        # Totais 10,00 (Produto Teste, R$ 10,00 x 1) e 20,00 (Produto Dois, R$ 20,00 x 1)
        self.itens = [
            ProductOrder.objects.create(
                order=self.pedido, product=produto, quantity=1,
                unit_value=produto.unit_value, total_value=produto.unit_value,
            )
            for produto in (self.produto, outro_produto)
        ]
        self.entrar(self.gerente)

    def test_detalhe_traz_os_itens_e_a_soma_dos_totais(self):
        resposta = self.client.get(reverse("order-detail", args=[self.pedido.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["product_orders"], self.itens)
        self.assertEqual(resposta.context["product_orders_total"], Decimal("30.00"))
