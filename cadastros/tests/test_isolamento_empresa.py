from decimal import Decimal

from django.urls import reverse

from cadastros.models import Client, Company, Order, OrderStatus, Product, ProductOrder

from .base import CadastrosTestCase


class IsolamentoPorEmpresaTests(CadastrosTestCase):
    """
    CB06 (TC-19): o ActiveCompanyRequiredMixin separa os dados por empresa ativa.
    get_queryset filtra por company (ou order__company, no ProductOrder) e
    get_form limita as opções das ForeignKeys à empresa ativa.
    """

    def setUp(self):
        super().setUp()
        # Empresa B, com cliente, produto e um pedido com item: nada disso pode vazar para a A
        self.empresa_b = Company.objects.create(name="Empresa B", cnpj="11111111000191", created_by=self.gerente)
        self.cliente_b = Client.objects.create(
            name="Cliente da B", cnpj_cpf="99999999999", uf="SP", company=self.empresa_b, created_by=self.gerente,
        )
        produto_b = Product.objects.create(
            name="Produto da B", sku="PB-1", unit_value=Decimal("5.00"), stock=5,
            company=self.empresa_b, created_by=self.gerente,
        )
        pedido_b = Order.objects.create(
            company=self.empresa_b, client=self.cliente_b, uf="SP", status=OrderStatus.APROVADO,
            total_value=Decimal("5.00"), created_by=self.gerente,
        )
        self.item_b = ProductOrder.objects.create(
            order=pedido_b, product=produto_b, quantity=1, unit_value=Decimal("5.00"), total_value=Decimal("5.00"),
        )

        self.item_a = self.criar_pedido(self.gerente, 1).product_orders.get()
        # Gerente da Empresa A, que vê todos os pedidos dela (RN02 não interfere)
        self.entrar(self.gerente)

    def test_lista_de_clientes_so_traz_os_da_empresa_ativa(self):
        resposta = self.client.get(reverse("client-list"))

        self.assertEqual(list(resposta.context["object_list"]), [self.cliente])
        self.assertNotContains(resposta, "Cliente da B")

    def test_detalhe_de_cliente_de_outra_empresa_da_404(self):
        resposta = self.client.get(reverse("client-detail", args=[self.cliente_b.pk]))

        self.assertEqual(resposta.status_code, 404)

    def test_lista_de_itens_filtra_pela_empresa_do_pedido(self):
        resposta = self.client.get(reverse("productorder-list"))

        self.assertEqual(list(resposta.context["object_list"]), [self.item_a])
        self.assertTrue(all(item.order.company_id == self.empresa.pk for item in resposta.context["object_list"]))

    def test_campo_cliente_do_pedido_so_oferece_clientes_da_empresa_ativa(self):
        resposta = self.client.get(reverse("order-create"))

        opcoes = resposta.context["form"].fields["client"].queryset
        self.assertEqual(list(opcoes), [self.cliente])
        self.assertNotIn(self.cliente_b, opcoes)
