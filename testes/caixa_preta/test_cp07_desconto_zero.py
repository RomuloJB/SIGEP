from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order
from cadastros.tests.base import CadastrosTestCase


class PedidoDescontoZeroTestCase(CadastrosTestCase):
    """
    CP07 (TC-8): desconto 0,00, o limite inferior aceito. O representante da
    Empresa A cria um pedido do Produto Teste (R$ 10,00, estoque 10) com
    quantidade 2 e desconto 0,00: o pedido é gravado com total R$ 20,00 e o
    estoque cai para 8.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_desconto_zero_e_gravado_com_o_valor_cheio(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="2", desconto="0.00"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.total_value, Decimal("20.00"))
        item = pedido.product_orders.get()
        self.assertEqual((item.quantity, item.discount), (2, Decimal("0.00")))

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 8)
