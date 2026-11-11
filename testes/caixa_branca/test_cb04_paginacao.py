from django.urls import reverse

from cadastros.models import Client
from cadastros.tests.base import CadastrosTestCase


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
