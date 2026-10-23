from decimal import Decimal

from django.urls import reverse

from cadastros.models import Order

from .base import CadastrosTestCase


class VisibilidadePedidosTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.pedido_rep1 = self.criar_pedido(self.rep1, quantidade=2)
        self.pedido_rep2 = self.criar_pedido(self.rep2, quantidade=3)

    def test_detalhe_do_pedido_abre_com_os_itens(self):
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("order-detail", args=[self.pedido_rep1.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Produto Teste")
        self.assertEqual(resposta.context["product_orders_total"], Decimal("20.00"))

    def test_representante_lista_so_os_proprios_pedidos(self):
        self.entrar(self.rep1)
        resposta = self.client.get(reverse("order-list"))

        self.assertEqual(list(resposta.context["object_list"]), [self.pedido_rep1])

    def test_gerente_lista_todos_os_pedidos_da_empresa(self):
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("order-list"))

        self.assertCountEqual(resposta.context["object_list"], [self.pedido_rep1, self.pedido_rep2])

    def test_representante_nao_acessa_pedido_de_outro(self):
        self.entrar(self.rep1)
        for nome in ("order-detail", "order-update", "order-delete", "order-duplicate"):
            with self.subTest(url=nome):
                resposta = self.client.get(reverse(nome, args=[self.pedido_rep2.pk]))
                self.assertEqual(resposta.status_code, 404)

        self.client.post(reverse("order-delete", args=[self.pedido_rep2.pk]))
        self.assertTrue(Order.objects.filter(pk=self.pedido_rep2.pk).exists())

    def test_representante_ve_so_os_itens_dos_proprios_pedidos(self):
        self.entrar(self.rep1)
        resposta = self.client.get(reverse("productorder-list"))

        self.assertEqual(
            [item.order_id for item in resposta.context["object_list"]], [self.pedido_rep1.pk],
        )
        formulario = self.client.get(reverse("productorder-create")).context["form"]
        self.assertEqual(list(formulario.fields["order"].queryset), [self.pedido_rep1])

    def test_painel_do_representante_conta_so_os_proprios_pedidos(self):
        self.entrar(self.rep1)
        resposta = self.client.get("/")

        self.assertEqual(resposta.context["qtd_vendas"], 1)
        self.assertEqual(list(resposta.context["ultimos_pedidos"]), [self.pedido_rep1])
