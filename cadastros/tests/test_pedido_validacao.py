from django.urls import reverse
from django.utils.html import escape

from cadastros.models import Order, ProductOrder

from .base import CadastrosTestCase


class PedidoQuantidadeInvalidaTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_com_quantidade_zero_nao_e_gravado(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade="0", desconto="0.00"))

        mensagem = "Quantidade inválida para o produto 'Produto Teste'."
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(ProductOrder.objects.exists())
        self.assertIn(mensagem, resposta.context["form"].non_field_errors())
        self.assertContains(resposta, escape(mensagem))

        resposta = self.client.get(reverse("product-detail", args=[self.produto.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["object"].stock, 10)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 10)
