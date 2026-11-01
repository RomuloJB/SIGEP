from decimal import Decimal

from django.urls import reverse

from cadastros.models import Client, Order, OrderStatus

from .base import CadastrosTestCase


class RelatorioVendasTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.criar_pedido(self.rep1, quantidade=2)  # aprovado: R$ 20
        self.criar_pedido(self.rep2, quantidade=3)  # aprovado: R$ 30
        # Pedido que ainda não é venda
        self.criar_pedido(self.rep1, quantidade=5, status=OrderStatus.PENDENTE)

    def test_relatorio_do_gerente_soma_as_vendas_da_empresa(self):
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("sales-report"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["qtd_pedidos"], 2)
        self.assertEqual(resposta.context["total_vendas"], Decimal("50.00"))
        self.assertEqual(resposta.context["ticket_medio"], Decimal("25.00"))
        self.assertEqual(
            [(linha["product__name"], linha["quantidade"]) for linha in resposta.context["por_produto"]],
            [("Produto Teste", 5)],
        )
        self.assertEqual(len(resposta.context["por_representante"]), 2)

    def test_relatorio_do_representante_so_tem_as_proprias_vendas(self):
        self.entrar(self.rep1)
        resposta = self.client.get(reverse("sales-report"))

        self.assertEqual(resposta.context["qtd_pedidos"], 1)
        self.assertEqual(resposta.context["total_vendas"], Decimal("20.00"))
        self.assertNotIn("por_representante", resposta.context)
        self.assertNotContains(resposta, "Vendas por representante")

    def test_relatorio_filtra_por_cliente(self):
        outro = Client.objects.create(
            name="Outro", cnpj_cpf="11111111111", uf="PR", company=self.empresa, created_by=self.gerente,
        )
        Order.objects.create(
            company=self.empresa, client=outro, uf="PR", status=OrderStatus.APROVADO,
            total_value=Decimal("100.00"), created_by=self.gerente,
        )
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("sales-report"), {"client_name": "outr"})

        self.assertEqual(resposta.context["qtd_pedidos"], 1)
        self.assertEqual(resposta.context["total_vendas"], Decimal("100.00"))
        self.assertEqual([linha["client__name"] for linha in resposta.context["por_cliente"]], ["Outro"])

    def test_menu_relatorios_abre_o_relatorio(self):
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("index"))

        self.assertContains(resposta, 'href="{}"'.format(reverse("sales-report")))
