from decimal import Decimal

from django.urls import reverse

from cadastros.models import Company, Order, Product, ProductOrder

from cadastros.tests.base import CadastrosTestCase


class ConferenciaDosItensDoPedidoTests(CadastrosTestCase):
    """
    CB07 (TC-20): desvios de PedidoFormMixin.form_valid e services.conferir_itens
    ao criar um pedido em /order/create/ (botão "enviar", que confere o estoque).
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def postar(self, dados):
        return self.client.post(reverse("order-create"), dados)

    def erros(self, resposta):
        self.assertEqual(resposta.status_code, 200)
        return resposta.context["form"].non_field_errors()

    def test_produto_com_id_nao_numerico_e_invalido(self):
        dados = self.dados_do_pedido()
        dados["product_id[]"] = ["abc"]

        resposta = self.postar(dados)

        self.assertIn("Produto inválido (id=abc).", self.erros(resposta))
        self.assertFalse(Order.objects.exists())

    def test_produto_de_outra_empresa_e_invalido(self):
        empresa_b = Company.objects.create(name="Empresa B", cnpj="11111111000191", created_by=self.gerente)
        produto_b = Product.objects.create(
            name="Produto da B", sku="PB-1", unit_value=Decimal("5.00"), stock=50,
            company=empresa_b, created_by=self.gerente,
        )
        dados = self.dados_do_pedido()
        dados["product_id[]"] = [produto_b.pk]

        resposta = self.postar(dados)

        self.assertIn("Produto inválido (id={}).".format(produto_b.pk), self.erros(resposta))
        self.assertFalse(Order.objects.exists())

    def test_um_item_sem_estoque_barra_o_pedido_inteiro(self):
        sem_estoque = Product.objects.create(
            name="Produto Escasso", sku="PE-1", unit_value=Decimal("8.00"), stock=1,
            company=self.empresa, created_by=self.gerente,
        )
        dados = self.dados_do_pedido(quantidade=2)
        dados["product_id[]"] = [self.produto.pk, sem_estoque.pk]
        dados["quantity[]"] = [2, 5]
        dados["discount[]"] = ["0", "0"]

        resposta = self.postar(dados)

        self.assertIn(
            "Estoque insuficiente para 'Produto Escasso': disponível 1, solicitado 5.", self.erros(resposta),
        )
        self.assertFalse(Order.objects.exists())
        self.assertFalse(ProductOrder.objects.exists())
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 10)

    def test_item_valido_grava_pedido_com_total_autor_empresa_e_baixa_estoque(self):
        # Produto Teste: R$ 10,00 e estoque 10 (base.py)
        resposta = self.postar(self.dados_do_pedido(quantidade=2, desconto="5.00"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.total_value, Decimal("15.00"))
        self.assertEqual(pedido.created_by, self.rep1)
        self.assertEqual(pedido.company, self.empresa)

        item = pedido.product_orders.get()
        self.assertEqual((item.product, item.quantity, item.discount), (self.produto, 2, Decimal("5.00")))
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 8)
