from decimal import Decimal

from django.urls import reverse

from cadastros import relatorios
from cadastros.models import Order, OrderStatus, Product

from .base import CadastrosTestCase


class RelatoriosGerenciaisTests(CadastrosTestCase):
    def setUp(self):
        super().setUp()
        # 2 aprovados (3 e 1 unidades), 1 rejeitado, 1 pendente e 1 rascunho
        self.criar_pedido(self.rep1, 3, OrderStatus.APROVADO)
        self.criar_pedido(self.rep2, 1, OrderStatus.APROVADO)
        self.criar_pedido(self.rep1, 2, OrderStatus.REJEITADO)
        self.criar_pedido(self.rep1, 4, OrderStatus.PENDENTE)
        self.criar_pedido(self.rep1, 5, OrderStatus.EM_DIGITACAO)
        self.pedidos = Order.objects.filter(company=self.empresa)
        self.vendas = self.pedidos.filter(status=OrderStatus.APROVADO)

    def test_funil_de_status_segue_o_ciclo_de_vida(self):
        funil = relatorios.funil_de_status(self.pedidos)
        self.assertEqual(funil["chaves"], ["digitacao", "pendente", "aprovado", "rejeitado", "cancelado"])
        self.assertEqual(funil["valores"], [1, 1, 2, 1, 0])

    def test_resumo_conta_so_aprovados_como_venda(self):
        resumo = relatorios.resumo_de_vendas(self.pedidos)
        self.assertEqual(resumo["total_vendido"], Decimal("40.00"))
        self.assertEqual(resumo["qtd_vendas"], 2)
        self.assertEqual(resumo["ticket_medio"], Decimal("20.00"))
        self.assertEqual(resumo["pendentes_qtd"], 1)
        self.assertEqual(resumo["pendentes_valor"], Decimal("40.00"))

    def test_taxa_de_aprovacao_usa_apenas_pedidos_decididos(self):
        # 2 aprovados e 1 rejeitado: 2 de 3
        self.assertAlmostEqual(relatorios.resumo_de_vendas(self.pedidos)["taxa_aprovacao"], 66.6667, places=3)

    def test_taxa_de_aprovacao_sem_pedidos_decididos_e_none(self):
        self.assertIsNone(relatorios.resumo_de_vendas(Order.objects.none())["taxa_aprovacao"])

    def test_vendas_por_forma_de_pagamento_usa_o_rotulo(self):
        serie = relatorios.vendas_por_forma_de_pagamento(self.vendas)
        self.assertEqual(serie["labels"], ["2 - Pix"])
        self.assertEqual(serie["valores"], [40.0])

    def test_vendas_por_representante_ordena_do_maior_para_o_menor(self):
        serie = relatorios.vendas_por_representante(self.vendas)
        self.assertEqual(serie["labels"], ["rep1", "rep2"])
        self.assertEqual(serie["valores"], [30.0, 10.0])

    def test_produtos_clientes_e_uf(self):
        itens = relatorios.itens_vendidos(self.vendas)
        self.assertEqual(relatorios.melhores_produtos(itens)["labels"], ["Produto Teste"])
        self.assertEqual(relatorios.melhores_clientes(self.vendas)["valores"], [40.0])
        self.assertEqual(relatorios.vendas_por_uf(self.vendas)["labels"], ["PR"])

    def test_descontos(self):
        pedido = self.vendas.first()
        item = pedido.product_orders.first()
        item.discount = Decimal("5.00")
        item.total_value -= Decimal("5.00")
        item.save()
        resultado = relatorios.descontos(relatorios.itens_vendidos(self.vendas))
        self.assertEqual(resultado["valor"], Decimal("5.00"))
        # 5 de desconto sobre 40 de valor de tabela (35 cobrados + 5 descontados)
        self.assertEqual(float(resultado["percentual"]), 12.5)

    def test_estoque_critico_lista_so_produtos_abaixo_do_limite(self):
        Product.objects.create(
            name="Cheio", sku="CH-1", unit_value=1, stock=500, company=self.empresa, created_by=self.gerente,
        )
        Product.objects.create(
            name="Quase acabando", sku="QA-1", unit_value=1, stock=2, company=self.empresa, created_by=self.gerente,
        )
        serie = relatorios.estoque_critico(self.empresa)
        self.assertEqual(serie["labels"], ["Quase acabando", "Produto Teste"])
        self.assertEqual(serie["valores"], [2.0, 10.0])

    def test_produtos_sem_venda(self):
        Product.objects.create(
            name="Encalhado", sku="EN-1", unit_value=1, stock=1, company=self.empresa, created_by=self.gerente,
        )
        itens = relatorios.itens_vendidos(self.vendas)
        self.assertEqual(relatorios.produtos_sem_venda(self.empresa, itens), 1)


class PainelGerencialViewTests(CadastrosTestCase):
    def setUp(self):
        super().setUp()
        self.criar_pedido(self.rep1, 3, OrderStatus.APROVADO)
        self.criar_pedido(self.rep2, 1, OrderStatus.APROVADO)
        self.url = reverse("management-report")

    def test_exige_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_gerente_ve_todos_os_pedidos_e_o_grafico_por_representante(self):
        self.entrar(self.gerente)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["qtd_vendas"], 2)
        self.assertIn("representantes", resposta.context["graficos"])
        self.assertContains(resposta, "grafico-representantes")

    def test_representante_ve_so_os_proprios_pedidos_sem_o_grafico_por_representante(self):
        self.entrar(self.rep1)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["qtd_vendas"], 1)
        self.assertNotIn("representantes", resposta.context["graficos"])
        self.assertNotContains(resposta, "grafico-representantes")

    def test_filtro_de_cliente_restringe_os_numeros(self):
        self.entrar(self.gerente)
        resposta = self.client.get(self.url, {"client_name": "nao existe"})
        self.assertEqual(resposta.context["qtd_vendas"], 0)
        self.assertEqual(resposta.context["graficos"]["status"]["valores"], [0, 0, 0, 0, 0])

    def test_nao_mistura_dados_de_outra_empresa(self):
        from cadastros.models import Client, Company, Order

        outra = Company.objects.create(name="Empresa B", cnpj="11111111000191", created_by=self.gerente)
        cliente_b = Client.objects.create(name="Cliente B", cnpj_cpf="1", uf="SC", company=outra, created_by=self.gerente)
        Order.objects.create(
            company=outra, client=cliente_b, uf="SC", status=OrderStatus.APROVADO,
            total_value=Decimal("999.00"), created_by=self.gerente,
        )
        self.entrar(self.gerente)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context["total_vendido"], Decimal("40.00"))
