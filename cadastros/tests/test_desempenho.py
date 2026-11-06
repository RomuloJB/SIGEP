from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cadastros.models import Client, Order, Product

from .base import CadastrosTestCase


class DesempenhoDasViewsTests(CadastrosTestCase):
    """
    Garante que as telas não fazem uma consulta por linha (N+1): o número de
    consultas é o mesmo com poucos e com muitos registros.
    """

    def consultas(self, url):
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        return len(capturadas)

    def criar_massa(self, qtd):
        for i in range(qtd):
            cliente = Client.objects.create(
                name="Cliente %d" % i, cnpj_cpf="00000000000", uf="PR", company=self.empresa, created_by=self.gerente,
            )
            produto = Product.objects.create(
                name="Produto %d" % i, sku="P-%d-%d" % (qtd, i), unit_value=10, stock=50,
                company=self.empresa, created_by=self.gerente,
            )
            pedido = self.criar_pedido(self.gerente, 2)
            pedido.client = cliente
            pedido.save()
            pedido.product_orders.update(product=produto)

    def test_telas_nao_repetem_consultas_por_linha(self):
        self.entrar(self.gerente)
        self.gerente.is_superuser = True
        self.gerente.save()
        telas = {
            "lista de pedidos": reverse("order-list"),
            "lista de itens": reverse("productorder-list"),
            "lista de clientes": reverse("client-list"),
            "lista de produtos": reverse("product-list"),
            "relatório de vendas": reverse("sales-report"),
            "dashboard": reverse("index"),
            "detalhe da empresa": reverse("company-detail", args=[self.empresa.pk]),
            "detalhe do cliente": reverse("client-detail", args=[self.cliente.pk]),
            "detalhe do produto": reverse("product-detail", args=[self.produto.pk]),
        }
        self.criar_massa(2)
        antes = {nome: self.consultas(url) for nome, url in telas.items()}
        self.criar_massa(6)
        for nome, url in telas.items():
            with self.subTest(tela=nome):
                self.assertEqual(self.consultas(url), antes[nome])

    def test_detalhe_do_pedido_nao_cresce_com_os_itens(self):
        self.entrar(self.gerente)
        pedido = self.criar_pedido(self.gerente, 1)
        url = reverse("order-detail", args=[pedido.pk])
        antes = self.consultas(url)
        for _ in range(5):
            pedido.product_orders.create(product=self.produto, quantity=1, unit_value=10, total_value=10)
        self.assertEqual(self.consultas(url), antes)

    def test_gravar_pedido_nao_consulta_um_produto_por_item(self):
        self.entrar(self.gerente)
        extras = [
            Product.objects.create(
                name="Extra %d" % i, sku="EX-%d" % i, unit_value=10, stock=50,
                company=self.empresa, created_by=self.gerente,
            )
            for i in range(5)
        ]
        dados = self.dados_do_pedido(acao="rascunho")
        with CaptureQueriesContext(connection) as um_item:
            self.client.post(reverse("order-create"), dados)
        dados["product_id[]"] = [self.produto.pk] + [p.pk for p in extras]
        dados["quantity[]"] = [1] * 6
        dados["discount[]"] = ["0"] * 6
        with CaptureQueriesContext(connection) as seis_itens:
            self.client.post(reverse("order-create"), dados)
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(len(seis_itens), len(um_item))
