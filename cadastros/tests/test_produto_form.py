from decimal import Decimal

from django.contrib.auth.models import Group
from django.urls import reverse

from cadastros.models import Product

from .base import CadastrosTestCase


class FormularioProdutoTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.gerente.groups.add(Group.objects.get_or_create(name="Manager")[0])
        self.entrar(self.gerente)

    def dados(self, **campos):
        return {
            "name": "Caderno", "description": "", "sku": "CAD-1", "color": "Azul",
            "measure_unit": "UND", "unit_value": "19.90", "stock": "5", **campos,
        }

    def test_campos_curtos_nao_ocupam_a_linha_inteira(self):
        resposta = self.client.get(reverse("product-create"))
        html = resposta.content.decode()

        for campo in ("sku", "color", "measure_unit", "unit_value", "stock"):
            with self.subTest(campo=campo):
                self.assertRegex(html, r'class="col-12 col-md-\d"\s*>\s*<div id="div_id_{}"'.format(campo))

    def test_criar_produto_vincula_a_empresa_ativa(self):
        self.client.post(reverse("product-create"), self.dados())

        produto = Product.objects.get(sku="CAD-1")
        self.assertEqual(produto.company, self.empresa)
        self.assertEqual(produto.created_by, self.gerente)
        self.assertEqual(produto.unit_value, Decimal("19.90"))

    def test_editar_produto(self):
        self.client.post(reverse("product-update", args=[self.produto.pk]), self.dados(name="Novo nome"))

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.name, "Novo nome")
