from django.contrib.auth import SESSION_KEY
from django.urls import reverse

from cadastros.tests.base import CadastrosTestCase


class LoginSenhaIncorretaTestCase(CadastrosTestCase):
    """
    CP11 (TC-12): login com senha incorreta. Sem ninguém logado, o
    representante de teste (rep1) informa uma senha errada: o acesso é negado,
    aparece a mensagem de credenciais inválidas e ele continua na tela de login.
    """

    def test_senha_incorreta_nega_o_acesso_e_fica_no_login(self):
        resposta = self.client.get(reverse("login"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "usuarios/login.html")
        self.assertContains(resposta, 'name="username"')
        self.assertContains(resposta, 'name="password"')

        resposta = self.client.post(reverse("login"), {"username": "rep1", "password": "senha-errada"})

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "usuarios/login.html")
        self.assertContains(resposta, "Usuário ou senha inválidos. Verifique e tente novamente.")
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertFalse(resposta.context["user"].is_authenticated)
