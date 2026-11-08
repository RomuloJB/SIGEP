import re

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from cadastros.models import Company, User_Profile
from website.templatetags.sidebar import iniciais

OPCOES_REPRESENTANTE = [
    "Dashboard", "Clientes", "Produtos", "Pedidos", "Importações", "Relatório de vendas", "Painel gerencial", "Sobre", "Meu consumo de IA",
]
OPCOES_ADMINISTRACAO = [
    "Gerenciar Usuários", "Requisições de IA", "Configuração da IA", "IA por usuário",
    "Log do Telegram", "Remetentes do Telegram", "Configuração do Telegram", "Configuração da importação",
]


class SidebarTests(TestCase):

    def setUp(self):
        self.gerente = User.objects.create_user("gerente", "gerente@sigep.test", "x")
        self.gerente.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.rep = User.objects.create_user("rep", "rep@sigep.test", "x")
        self.admin = User.objects.create_superuser("admin", "admin@sigep.test", "x")
        User_Profile.objects.create(user=self.gerente, name="Marina Silva", phone="41999999999", cpf="52998224725")

        self.empresa = Company.objects.create(
            name="Empresa Comprida Ltda", session_name="Apelido", cnpj="00000000000191", created_by=self.gerente,
        )
        self.empresa.manager.add(self.gerente, self.admin)
        self.empresa.sales_rep.add(self.rep)

    def entrar(self, usuario):
        self.client.force_login(usuario)
        sessao = self.client.session
        sessao["active_company_id"] = self.empresa.pk
        sessao["company_name"] = self.empresa.display_name
        sessao.save()

    def html(self, rota="index"):
        return self.client.get(reverse(rota)).content.decode()

    def opcoes(self, rota="index"):
        return re.findall(r'app-sidebar__rotulo">([^<]+)<', self.html(rota))

    def opcao_atual(self, rota):
        return re.findall(r'aria-current="page">.*?app-sidebar__rotulo">([^<]+)<', self.html(rota), re.S)

    def test_representante_ve_so_as_opcoes_do_perfil(self):
        self.entrar(self.rep)

        self.assertEqual(self.opcoes(), OPCOES_REPRESENTANTE)

    def test_gerente_tambem_ve_empresas(self):
        self.entrar(self.gerente)

        self.assertEqual(self.opcoes(), ["Dashboard", "Empresas", *OPCOES_REPRESENTANTE[1:]])

    def test_superusuario_tambem_ve_a_administracao(self):
        self.entrar(self.admin)

        self.assertEqual(self.opcoes(), ["Dashboard", "Empresas", *OPCOES_REPRESENTANTE[1:], *OPCOES_ADMINISTRACAO])

    def test_visitante_ve_entrar_e_sobre(self):
        self.assertEqual(self.opcoes("about"), ["Entrar", "Sobre"])

    def test_opcao_da_pagina_atual_fica_marcada(self):
        self.entrar(self.gerente)
        casos = [
            ("index", "Dashboard"),
            ("client-list", "Clientes"),
            ("client-create", "Clientes"),
            ("product-list", "Produtos"),
            ("order-create", "Pedidos"),
            ("productorder-list", "Pedidos"),
            ("sales-report", "Relatório de vendas"),
            ("management-report", "Painel gerencial"),
            ("ia:meu-consumo", "Meu consumo de IA"),
        ]
        for rota, opcao in casos:
            with self.subTest(rota=rota):
                self.assertEqual(self.opcao_atual(rota), [opcao])

    def test_pagina_fora_do_menu_nao_marca_nenhuma_opcao(self):
        self.entrar(self.gerente)

        self.assertEqual(self.opcao_atual("my-profile"), [])

    def test_mostra_empresa_papel_e_usuario(self):
        self.entrar(self.gerente)
        html = self.html()

        self.assertIn("Apelido", html)
        self.assertRegex(html, r"card-company-topnav__papel\">Gerente")
        self.assertIn("Marina Silva", html)
        self.assertIn(">MS</span>", html)
        self.assertIn('href="{}"'.format(reverse("my-profile")), html)

    def test_logo_e_troca_de_empresa_ficam_na_barra_superior(self):
        self.entrar(self.rep)
        barra, resto = self.html().split("<aside", 1)
        sidebar = resto.split("</aside>", 1)[0]
        troca = 'href="{}"'.format(reverse("select-company"))

        self.assertRegex(barra, r'navbar-brand[^>]*>\s*<img src="[^"]*favicon-sigep')
        self.assertIn(troca, barra)
        self.assertNotIn("favicon-sigep", sidebar)
        self.assertNotIn(troca, sidebar)

    def test_sem_empresa_ativa_convida_a_selecionar(self):
        self.client.force_login(self.rep)
        html = self.html("about")

        self.assertIn("Selecionar empresa", html)
        self.assertNotIn("card-company-topnav__papel", html)

    def test_visitante_nao_ve_a_troca_de_empresa(self):
        self.assertNotIn("card-company-topnav", self.html("about"))

    def test_usuario_sem_perfil_aparece_pelo_login(self):
        self.entrar(self.admin)
        html = self.html()

        self.assertRegex(html, r"card-company-topnav__papel\">Administrador")
        self.assertIn('data-rotulo="admin"', html)
        self.assertIn(">A</span>", html)


class IniciaisTests(SimpleTestCase):

    def test_usa_a_primeira_e_a_ultima_palavra(self):
        self.assertEqual(iniciais("Marina Duarte Silva"), "MS")

    def test_nome_de_uma_palavra_tem_uma_letra(self):
        self.assertEqual(iniciais("admin"), "A")

    def test_nome_vazio_nao_quebra(self):
        self.assertEqual(iniciais("  "), "?")
