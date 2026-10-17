from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Client, Company, Order, Product, ProductOrder


class PedidosTestCase(TestCase):

    def setUp(self):
        self.gerente = User.objects.create_user("gerente", email="gerente@sigep.test", password="x")
        self.rep1 = User.objects.create_user("rep1", email="rep1@sigep.test", password="x")
        self.rep2 = User.objects.create_user("rep2", email="rep2@sigep.test", password="x")

        self.empresa = Company.objects.create(name="Empresa", cnpj="00000000000191", created_by=self.gerente)
        self.empresa.manager.add(self.gerente)
        self.empresa.sales_rep.add(self.rep1, self.rep2)

        self.cliente = Client.objects.create(
            name="Cliente", cnpj_cpf="00000000000", uf="PR", company=self.empresa, created_by=self.gerente,
        )
        self.produto = Product.objects.create(
            name="Caneta", sku="CAN-1", unit_value=Decimal("10.00"), stock=10,
            company=self.empresa, created_by=self.gerente,
        )

        self.pedido_rep1 = self.criar_pedido(self.rep1, quantidade=2)
        self.pedido_rep2 = self.criar_pedido(self.rep2, quantidade=3)

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

    def entrar(self, usuario):
        self.client.force_login(usuario)
        sessao = self.client.session
        sessao["active_company_id"] = self.empresa.pk
        sessao.save()

    def dados_do_pedido(self, quantidade=1, desconto="0"):
        return {
            "type": "OUT", "client": self.cliente.pk, "payment_method": "pix", "uf": "PR",
            "address": "", "city": "",
            "product_id[]": [self.produto.pk], "quantity[]": [quantidade], "discount[]": [desconto],
        }

    # RF13
    def test_detalhe_do_pedido_abre_com_os_itens(self):
        self.entrar(self.gerente)
        resposta = self.client.get(reverse("order-detail", args=[self.pedido_rep1.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Caneta")
        self.assertEqual(resposta.context["product_orders_total"], Decimal("20.00"))

    # RF15 / RN02
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

    # RF07
    def test_pedido_salvo_avisa_os_gerentes_por_email(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=2))

        self.assertEqual(resposta.status_code, 302)
        novo = Order.objects.latest("id")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["gerente@sigep.test"])
        self.assertIn("#{}".format(novo.pk), mail.outbox[0].subject)
        self.assertIn("2 x Caneta", mail.outbox[0].body)
        self.assertIn(reverse("order-detail", args=[novo.pk]), mail.outbox[0].body)

    def test_gerente_que_cria_o_pedido_nao_recebe_o_proprio_aviso(self):
        self.entrar(self.gerente)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("order-create"), self.dados_do_pedido())

        self.assertEqual(len(mail.outbox), 0)

    def test_pedido_com_erro_nao_envia_email(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=999))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        # A tabela de itens volta com o que foi enviado
        self.assertEqual(resposta.context["itens_iniciais"][0]["quantity"], "999")

    # RF12
    def test_duplicar_preenche_cabecalho_e_itens_do_original(self):
        self.entrar(self.rep1)
        resposta = self.client.get(reverse("order-duplicate", args=[self.pedido_rep1.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["form"].initial["client"], self.cliente.pk)
        self.assertEqual(
            resposta.context["itens_iniciais"],
            [{"product_id": self.produto.pk, "quantity": 2, "discount": Decimal("0")}],
        )
        self.assertContains(resposta, 'id="itens-iniciais"')

    def test_salvar_duplicacao_cria_outro_pedido_e_baixa_estoque(self):
        self.entrar(self.rep1)
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
