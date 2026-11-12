from django.urls import reverse
from django.utils.html import escape

from cadastros.models import Order, ProductOrder
from cadastros.tests.base import CadastrosTestCase


class PedidoSemItensTestCase(CadastrosTestCase):
    """
    CP10 (TC-11): pedido sem itens. O representante da Empresa A preenche o
    cabeçalho do pedido (Cliente Teste, Pix, PR) sem adicionar nenhum produto
    e clica em "Criar Pedido": o pedido não é gravado.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_pedido_sem_itens_nao_e_gravado(self):
        resposta = self.client.get(reverse("order-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/order_form.html")

        dados = self.dados_do_pedido()
        for campo in ("product_id[]", "quantity[]", "discount[]"):
            del dados[campo]
        resposta = self.client.post(reverse("order-create"), dados)

        mensagem = "Adicione pelo menos um produto ao pedido."
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(ProductOrder.objects.exists())
        self.assertIn(mensagem, resposta.context["form"].non_field_errors())
        self.assertContains(resposta, escape(mensagem))
