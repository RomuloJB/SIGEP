from decimal import Decimal
from html import unescape

from django.template import Context, Template
from django.test import RequestFactory
from django.urls import reverse

from cadastros.models import Product

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
