from django.contrib.auth.models import User
from django.urls import reverse

from .base import CadastrosTestCase


class BotaoVoltarTests(CadastrosTestCase):
    def test_formularios_tem_botao_voltar_com_history_back(self):
        admin = User.objects.create_superuser("admin", email="admin@sigep.test", password="senha-teste-123")
        self.empresa.manager.add(admin)
        self.entrar(admin)
        for nome in ("client-create", "product-create", "company-create"):
            with self.subTest(tela=nome):
                resposta = self.client.get(reverse(nome))
                self.assertContains(resposta, "btn-voltar")
                self.assertContains(resposta, "history.back()")
