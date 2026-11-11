from decimal import Decimal
from html import unescape

from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse

from cadastros.models import Client, Product

from .base import CadastrosTestCase


class UrlPaginaTests(CadastrosTestCase):
    def renderizar(self, querystring, numero):
        request = RequestFactory().get("/product/" + querystring)
        template = Template("{% load paginacao %}{% url_pagina n %}")
        # O template escapa & como &amp; (correto dentro de um href)
        return unescape(template.render(Context({"request": request, "n": numero})))

    def test_troca_so_o_page_e_mantem_filtros(self):
        url = self.renderizar("?name=caneta&color=azul&page=2", 3)
        parametros = dict(p.split("=") for p in url.lstrip("?").split("&"))
        self.assertEqual(parametros, {"name": "caneta", "color": "azul", "page": "3"})

    def test_sem_filtros_so_tem_o_page(self):
        self.assertEqual(self.renderizar("", 2), "?page=2")

    def test_preserva_campos_com_varios_valores_e_escapa(self):
        url = self.renderizar("?uf=PR&uf=SC&name=a%20b%26c", 4)
        self.assertEqual(url.count("uf="), 2)
        self.assertIn("name=a+b%26c", url.replace("%20", "+"))
        self.assertTrue(url.endswith("page=4") or "page=4" in url)


class PaginacaoComFiltroTests(CadastrosTestCase):
    def setUp(self):
        super().setUp()
        for i in range(25):
            Product.objects.create(
                name="Caneta %02d" % i, sku="CAN-%02d" % i, unit_value=Decimal("5.00"),
                stock=10, company=self.empresa, created_by=self.gerente,
            )
        self.entrar(self.gerente)

    def test_links_de_pagina_mantem_o_filtro(self):
        resposta = self.client.get(reverse("product-list"), {"name": "caneta"})
        self.assertContains(resposta, "name=caneta&amp;page=2")

    def test_segunda_pagina_filtrada_traz_os_registros_restantes(self):
        resposta = self.client.get(reverse("product-list"), {"name": "caneta", "page": 3})
        self.assertEqual(len(resposta.context["object_list"]), 5)
        self.assertNotContains(resposta, "Produto Teste")


class TamanhoDaPaginaTests(CadastrosTestCase):
    """
    CB04 (TC-17): get_paginate_by das listagens. O PaginatedFilterView pagina
    sempre com 10 itens e ignora o ?per_page (o seletor foi removido no commit
    083e04c); os relatórios sobrescrevem get_paginate_by para devolver None e
    calcular os totais sobre todos os pedidos filtrados.
    """

    def setUp(self):
        super().setUp()
        # 1 cliente do base + 24 = 25, mais de duas páginas de 10
        for i in range(24):
            Client.objects.create(
                name="Cliente %02d" % i, cnpj_cpf="%011d" % (i + 1), uf="PR",
                company=self.empresa, created_by=self.gerente,
            )
        self.entrar(self.gerente)

    def tamanho_da_pagina(self, **parametros):
        resposta = self.client.get(reverse("client-list"), parametros)
        self.assertEqual(resposta.status_code, 200)
        return resposta.context["page_obj"].paginator.per_page

    def test_sem_per_page_usa_o_padrao_de_10(self):
        self.assertEqual(self.tamanho_da_pagina(), 10)

    def test_per_page_numerico_e_ignorado(self):
        # 20 era uma das opções do seletor removido: não muda mais o tamanho
        self.assertEqual(self.tamanho_da_pagina(per_page=20), 10)
        self.assertEqual(self.tamanho_da_pagina(per_page=15), 10)

    def test_per_page_invalido_nao_quebra_a_listagem(self):
        self.assertEqual(self.tamanho_da_pagina(per_page="abc"), 10)

    def test_relatorios_nao_paginam(self):
        for rota in ("sales-report", "management-report"):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota), {"per_page": 20})
                self.assertEqual(resposta.status_code, 200)
                self.assertFalse(resposta.context["is_paginated"])
                self.assertIsNone(resposta.context["page_obj"])
