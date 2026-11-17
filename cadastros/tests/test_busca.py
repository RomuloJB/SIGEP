from html import unescape

from django.contrib.auth.models import User
from django.urls import reverse

from cadastros.models import Client, Company, Order, OrderStatus

from .base import CadastrosTestCase


class BuscaGeralTests(CadastrosTestCase):
    """O campo "Buscar" das listagens procura em todos os registros (?q=), não só na página atual."""

    def setUp(self):
        super().setUp()
        # 1 cliente do base + 24 = 25: três páginas de 10
        for i in range(24):
            Client.objects.create(
                name="Cliente %02d" % i, cnpj_cpf="%011d" % (i + 1), uf="SC",
                company=self.empresa, created_by=self.gerente,
            )
        # Fica na última página da lista sem busca (ordem por nome)
        self.joao = Client.objects.create(
            name="Zé João Conceição", cnpj_cpf="12345678909", uf="SP", company=self.empresa, created_by=self.gerente,
        )
        self.entrar(self.gerente)

    def clientes(self, **parametros):
        resposta = self.client.get(reverse("client-list"), parametros)
        self.assertEqual(resposta.status_code, 200)
        return resposta, [c.name for c in resposta.context["object_list"]]

    def test_acha_registro_que_esta_fora_da_primeira_pagina(self):
        resposta, nomes = self.clientes()
        self.assertNotIn(self.joao.name, nomes)

        resposta, nomes = self.clientes(q="conceição")

        self.assertEqual(nomes, [self.joao.name])
        self.assertEqual(resposta.context["page_obj"].paginator.count, 1)

    def test_ignora_maiusculas_e_acentos_nos_dois_lados(self):
        for termo in ("JOAO", "joão", "conceicao", "ze"):
            with self.subTest(termo=termo):
                self.assertEqual(self.clientes(q=termo)[1], [self.joao.name])

    def test_cada_palavra_precisa_aparecer_em_algum_campo(self):
        self.assertEqual(self.clientes(q="joao sp")[1], [self.joao.name])
        self.assertEqual(self.clientes(q="joao sc")[1], [])

    def test_cpf_com_ou_sem_mascara_e_id(self):
        for termo in ("123.456.789-09", "45678", str(self.joao.pk), "#{}".format(self.joao.pk)):
            with self.subTest(termo=termo):
                self.assertIn(self.joao.name, self.clientes(q=termo)[1])

    def test_busca_pagina_e_vale_junto_com_o_filtro(self):
        resposta, nomes = self.clientes(q="cliente")
        self.assertEqual(resposta.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(nomes), 10)

        # A página 3 da busca continua buscando (a paginação repete o ?q=)
        resposta, nomes = self.clientes(q="cliente", page=3)
        self.assertEqual(len(nomes), 5)
        self.assertIn("q=cliente", unescape(resposta.content.decode()))

        # Filtro do django-filter + busca: os dois valem
        self.assertEqual(self.clientes(q="cliente", uf="PR")[1], ["Cliente Teste"])

    def test_campo_mostra_a_busca_e_guarda_os_filtros(self):
        resposta, _ = self.clientes(q="joão", uf="SP", page=1)
        html = resposta.content.decode()

        self.assertIn('name="q" value="joão"', html)
        # O filtro ativo vai junto na próxima busca; a página volta para a 1
        self.assertIn('<input type="hidden" name="uf" value="SP">', html)
        self.assertNotIn('name="page"', html)
        # E o formulário de filtros mantém a busca
        self.assertIn('<input type="hidden" name="q" value="joão">', html)

    def test_busca_vazia_ou_so_com_espacos_mostra_tudo(self):
        self.assertEqual(self.clientes(q="   ")[0].context["page_obj"].paginator.count, 26)

    def test_respeita_a_empresa_ativa(self):
        outra = Company.objects.create(name="Empresa B", cnpj="11222333000181", created_by=self.gerente)
        Client.objects.create(name="João de Outra Empresa", cnpj_cpf="98765432100", uf="SP",
                              company=outra, created_by=self.gerente)

        self.assertEqual(self.clientes(q="joao")[1], [self.joao.name])

    def test_pedidos_pelo_rotulo_do_status_e_da_forma_de_pagamento(self):
        aprovado = self.criar_pedido(self.gerente, 1, status=OrderStatus.APROVADO)
        rejeitado = self.criar_pedido(self.gerente, 1, status=OrderStatus.REJEITADO)
        Order.objects.filter(pk=rejeitado.pk).update(payment_method="boleto 30dias")

        def pedidos(termo):
            resposta = self.client.get(reverse("order-list"), {"q": termo})
            return [p.pk for p in resposta.context["object_list"]]

        self.assertEqual(pedidos("aprovado"), [aprovado.pk])
        self.assertEqual(pedidos("boleto(30)"), [rejeitado.pk])
        self.assertEqual(pedidos("#{}".format(rejeitado.pk)), [rejeitado.pk])
        self.assertEqual(sorted(pedidos("cliente teste")), sorted([aprovado.pk, rejeitado.pk]))

    def test_termo_que_nao_existe_mostra_lista_vazia(self):
        self.assertEqual(self.clientes(q="xyzxyz")[1], [])


class BuscaGeralUsuariosTests(CadastrosTestCase):
    """Gerenciar Usuários é uma ListView sem django-filter: a busca entra pelo get_queryset."""

    def test_busca_usuario_pelo_login_e_email(self):
        admin = User.objects.create_superuser("admin", "admin@sigep.test", "x")
        self.client.force_login(admin)

        resposta = self.client.get(reverse("user-list"), {"q": "rep2@"})

        self.assertEqual([u.username for u in resposta.context["users"]], ["rep2"])
        self.assertContains(resposta, 'name="q" value="rep2@"')
