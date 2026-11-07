from decimal import Decimal

from django.contrib.auth.models import User

from cadastros import consultas
from cadastros.models import Company, OrderStatus, Product

from .base import CadastrosTestCase


class EmpresasDoUsuarioTestCase(CadastrosTestCase):

    def test_gerente_e_representante_entram_na_empresa(self):
        for usuario in (self.gerente, self.rep1):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(list(consultas.empresas_do_usuario(usuario)), [self.empresa])

    def test_quem_e_gerente_e_representante_aparece_uma_vez(self):
        self.empresa.sales_rep.add(self.gerente)

        self.assertEqual(list(consultas.empresas_do_usuario(self.gerente)), [self.empresa])

    def test_superusuario_entra_em_todas(self):
        admin = User.objects.create_superuser("admin", password="x")
        outra = Company.objects.create(name="Outra", cnpj="11111111000191", created_by=admin)

        self.assertCountEqual(consultas.empresas_do_usuario(admin), [self.empresa, outra])

    def test_quem_nao_esta_na_empresa_nao_entra(self):
        estranho = User.objects.create_user("estranho", password="x")

        self.assertFalse(consultas.empresas_do_usuario(estranho).exists())


class PedidosVisiveisTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.do_rep1 = self.criar_pedido(self.rep1, 1)
        self.do_rep2 = self.criar_pedido(self.rep2, 1, status=OrderStatus.PENDENTE)

    def test_gerente_ve_todos(self):
        self.assertTrue(consultas.ve_todos_os_pedidos(self.gerente, self.empresa))
        self.assertCountEqual(consultas.pedidos_visiveis(self.gerente, self.empresa), [self.do_rep1, self.do_rep2])

    def test_representante_ve_so_os_seus(self):
        self.assertFalse(consultas.ve_todos_os_pedidos(self.rep1, self.empresa))
        self.assertEqual(list(consultas.pedidos_visiveis(self.rep1, self.empresa)), [self.do_rep1])

    def test_ve_todos_informado_evita_a_consulta(self):
        with self.assertNumQueries(0):
            consultas.pedidos_visiveis(self.rep1, self.empresa, ve_todos=False)


class ProdutosTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.caderno = self.produto_com(name="Caderno 96 folhas", sku="CAD-096", stock=3)
        self.caneta = self.produto_com(name="Caneta azul", sku="CAN-AZ", stock=200)
        outra = Company.objects.create(name="Outra", cnpj="11111111000191", created_by=self.gerente)
        self.de_outra = self.produto_com(name="Caderno da outra", sku="CAD-OUT", stock=0, company=outra)

    def produto_com(self, **campos):
        dados = {"unit_value": Decimal("5.00"), "company": self.empresa, "created_by": self.gerente, **campos}
        return Product.objects.create(**dados)

    def test_busca_pelo_nome_ou_pelo_sku_so_na_empresa(self):
        self.assertEqual(list(consultas.buscar_produtos(self.empresa, "caderno")), [self.caderno])
        self.assertEqual(list(consultas.buscar_produtos(self.empresa, "can-az")), [self.caneta])

    def test_estoque_baixo_do_menor_para_o_maior(self):
        # O "Produto Teste" da base tem 10 unidades: o limite entra
        self.assertEqual(
            list(consultas.produtos_com_estoque_baixo(self.empresa)), [self.caderno, self.produto],
        )
