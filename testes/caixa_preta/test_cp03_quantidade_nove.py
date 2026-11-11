from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order
from cadastros.tests.base import CadastrosTestCase


class PedidoQuantidadeAbaixoDoEstoqueTestCase(CadastrosTestCase):
    """
    CP03 (TC-4): quantidade 9, imediatamente abaixo do estoque. O representante
    da Empresa A cria um pedido do Produto Teste (R$ 10,00, estoque 10) com
    quantidade 9: o pedido é gravado com total R$ 90,00 e o estoque cai para 1.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_quantidade_nove_e_gravado_e_deixa_estoque_um(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="9", desconto="0.00"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.total_value, Decimal("90.00"))
        self.assertEqual(pedido.product_orders.get().quantity, 9)

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 1)
