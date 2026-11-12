from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order
from cadastros.tests.base import CadastrosTestCase


class PedidoDescontoIgualAoSubtotalTestCase(CadastrosTestCase):
    """
    CP08 (TC-9): desconto 20,00, igual ao subtotal do item. O representante da
    Empresa A cria um pedido do Produto Teste (R$ 10,00, estoque 10) com
    quantidade 2 e desconto 20,00: o pedido é gravado com total R$ 0,00 e o
    estoque cai para 8.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_desconto_igual_ao_subtotal_e_gravado_com_total_zero(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="2", desconto="20.00"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.total_value, Decimal("0.00"))
        item = pedido.product_orders.get()
        self.assertEqual((item.quantity, item.discount), (2, Decimal("20.00")))

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 8)
