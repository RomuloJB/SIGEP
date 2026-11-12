from django.urls import reverse
from django.utils.html import escape

from cadastros.models import Client
from cadastros.tests.base import CadastrosTestCase


class ClienteDocumentoDozeDigitosTestCase(CadastrosTestCase):
    """
    CP12 (TC-13): CPF/CNPJ com 12 dígitos, classe inválida (nem CPF com 11 nem
    CNPJ com 14). O representante da Empresa A tenta cadastrar um cliente com
    esse documento: o cliente não é gravado e a tela pede um CPF ou CNPJ.
    """

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def test_cliente_com_documento_de_12_digitos_nao_e_gravado(self):
        resposta = self.client.get(reverse("client-create"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "cadastros/client_form.html")

        resposta = self.client.post(reverse("client-create"), {
            "name": "Cliente CP12", "cnpj_cpf": "123456789012", "uf": "PR", "address": "", "city": "",
        })

        mensagem = "Informe um CPF (000.000.000-00) ou CNPJ (00.000.000/0000-00)."
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Client.objects.filter(name="Cliente CP12").exists())
        self.assertIn(mensagem, resposta.context["form"].errors["cnpj_cpf"])
        self.assertContains(resposta, escape(mensagem))
