from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from cadastros.models import Client, Company, Order, Product, ProductOrder


class CadastrosTestCase(TestCase):

    def setUp(self):
        self.gerente = User.objects.create_user("gerente", email="gerente@sigep.test", password="x")
        self.rep1 = User.objects.create_user("rep1", email="rep1@sigep.test", password="x")
        self.rep2 = User.objects.create_user("rep2", email="rep2@sigep.test", password="x")

        self.empresa = Company.objects.create(name="Empresa A", cnpj="00000000000191", created_by=self.gerente)
        self.empresa.manager.add(self.gerente)
        self.empresa.sales_rep.add(self.rep1, self.rep2)

        self.cliente = Client.objects.create(
            name="Cliente Teste", cnpj_cpf="00000000000", uf="PR", company=self.empresa, created_by=self.gerente,
        )
        self.produto = Product.objects.create(
            name="Produto Teste", sku="PT-1", unit_value=Decimal("10.00"), stock=10,
            company=self.empresa, created_by=self.gerente,
        )

    def entrar(self, usuario):
        self.client.force_login(usuario)
        sessao = self.client.session
        sessao["active_company_id"] = self.empresa.pk
        sessao.save()

    def criar_pedido(self, autor, quantidade):
        pedido = Order.objects.create(
            company=self.empresa, client=self.cliente, uf="PR",
            total_value=self.produto.unit_value * quantidade, created_by=autor,
        )
        ProductOrder.objects.create(
            order=pedido, product=self.produto, quantity=quantidade,
            unit_value=self.produto.unit_value, total_value=self.produto.unit_value * quantidade,
        )
        return pedido

    def dados_do_pedido(self, quantidade=1, desconto="0"):
        return {
            "type": "OUT", "client": self.cliente.pk, "payment_method": "pix", "uf": "PR",
            "address": "", "city": "",
            "product_id[]": [self.produto.pk], "quantity[]": [quantidade], "discount[]": [desconto],
        }
