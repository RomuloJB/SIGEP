from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order
from cadastros.tests.base import CadastrosTestCase


class PedidoQuantidadeIgualAoEstoqueTestCase(CadastrosTestCase):
    """
    CP04 (TC-5): quantidade 10, igual ao estoque. O representante da Empresa A
    cria um pedido do Produto Teste (R$ 10,00, estoque 10) com quantidade 10:
    o pedido é gravado com total R$ 100,00 e o estoque zera.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_quantidade_igual_ao_estoque_e_gravado_e_zera_o_estoque(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="10", desconto="0.00"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.total_value, Decimal("100.00"))
        self.assertEqual(pedido.product_orders.get().quantity, 10)

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 0)
