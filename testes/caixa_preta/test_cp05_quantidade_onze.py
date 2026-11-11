from django.urls import reverse
from django.utils.html import escape

from cadastros.models import Order, ProductOrder
from cadastros.tests.base import CadastrosTestCase


class PedidoQuantidadeAcimaDoEstoqueTestCase(CadastrosTestCase):
    """
    CP05 (TC-6): quantidade 11, acima do estoque. O representante da Empresa A
    tenta criar um pedido do Produto Teste (R$ 10,00, estoque 10) com
    quantidade 11: o pedido não é gravado e o estoque continua 10.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_quantidade_acima_do_estoque_nao_e_gravado(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="11", desconto="0.00"))

        mensagem = "Estoque insuficiente para 'Produto Teste': disponível 10, solicitado 11."
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(ProductOrder.objects.exists())
        self.assertIn(mensagem, resposta.context["form"].non_field_errors())
        self.assertContains(resposta, escape(mensagem))

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 10)
