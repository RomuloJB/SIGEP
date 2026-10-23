from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order

from .base import CadastrosTestCase


class DuplicacaoPedidoTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.pedido_rep1 = self.criar_pedido(self.rep1, quantidade=2)
        self.entrar(self.rep1)

    def test_duplicar_preenche_cabecalho_e_itens_do_original(self):
        resposta = self.client.get(reverse("order-duplicate", args=[self.pedido_rep1.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["form"].initial["client"], self.cliente.pk)
        self.assertEqual(
            resposta.context["itens_iniciais"],
            [{"product_id": self.produto.pk, "quantity": 2, "discount": Decimal("0")}],
        )
        self.assertContains(resposta, 'id="itens-iniciais"')

    def test_salvar_duplicacao_cria_outro_pedido_e_baixa_estoque(self):
        url = reverse("order-duplicate", args=[self.pedido_rep1.pk])
        self.client.post(url, self.dados_do_pedido(quantidade=2))

        novo = Order.objects.latest("id")
        self.assertNotEqual(novo.pk, self.pedido_rep1.pk)
        self.assertEqual(novo.created_by, self.rep1)
        self.assertEqual(novo.total_value, Decimal("20.00"))
        self.assertEqual(novo.product_orders.count(), 1)
        self.assertEqual(self.pedido_rep1.product_orders.count(), 1)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 8)
