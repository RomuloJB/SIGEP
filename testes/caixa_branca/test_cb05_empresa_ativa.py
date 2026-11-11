from django.contrib.auth.models import User
from django.urls import reverse

from cadastros.models import Company

from cadastros.tests.base import CadastrosTestCase


class EmpresaAtivaObrigatoriaTests(CadastrosTestCase):
    """
    CB05 (TC-18): desvios do ActiveCompanyRequiredMixin.dispatch, exercitados
    pela listagem de clientes (/client/).
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("client-list")
        # Empresa B: sem vínculo com gerente, rep1 ou rep2
        self.empresa_b = Company.objects.create(
            name="Empresa B", cnpj="11111111000191", created_by=self.gerente,
        )

    def gravar_empresa_na_sessao(self, empresa):
        sessao = self.client.session
        sessao["active_company_id"] = empresa.pk
        sessao["company_name"] = empresa.display_name
        sessao.save()

    def test_sem_login_redireciona_para_o_login(self):
        resposta = self.client.get(self.url)

        self.assertRedirects(resposta, "{}?next={}".format(reverse("login"), self.url))

    def test_logado_sem_empresa_na_sessao_redireciona_para_a_selecao(self):
        self.client.force_login(self.rep1)

        resposta = self.client.get(self.url)

        self.assertRedirects(resposta, reverse("select-company"), fetch_redirect_response=False)

    def test_empresa_sem_vinculo_e_limpa_da_sessao(self):
        self.client.force_login(self.rep1)
        self.gravar_empresa_na_sessao(self.empresa_b)

        resposta = self.client.get(self.url)

        self.assertRedirects(resposta, reverse("select-company"), fetch_redirect_response=False)
        self.assertNotIn("active_company_id", self.client.session)
        self.assertNotIn("company_name", self.client.session)

    def test_superusuario_acessa_qualquer_empresa(self):
        admin = User.objects.create_superuser("admin", email="admin@sigep.test", password="x")
        self.client.force_login(admin)
        self.gravar_empresa_na_sessao(self.empresa_b)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.client.session["active_company_id"], self.empresa_b.pk)

    def test_representante_acessa_a_propria_empresa(self):
        self.client.force_login(self.rep1)
        self.gravar_empresa_na_sessao(self.empresa)

        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Cliente Teste")
