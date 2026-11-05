from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from erros import views


class PaginasDeErroTests(TestCase):
    def test_404_usa_pagina_propria(self):
        resposta = self.client.get("/essa-rota-nao-existe/")
        self.assertEqual(resposta.status_code, 404)
        self.assertTemplateUsed(resposta, "erros/erro.html")
        self.assertContains(resposta, "Página não encontrada", status_code=404)

    def test_404_abre_sem_login_e_sem_consultar_o_banco(self):
        with self.assertNumQueries(0):
            resposta = Client().get("/essa-rota-nao-existe/")
        self.assertEqual(resposta.status_code, 404)

    def test_500_renderiza_sem_request_e_sem_banco(self):
        with self.assertNumQueries(0):
            resposta = views.erro_500(RequestFactory().get("/"))
        self.assertEqual(resposta.status_code, 500)
        self.assertIn("Erro no servidor", resposta.content.decode())

    def test_400_e_403(self):
        pedido = RequestFactory().get("/")
        self.assertEqual(views.erro_400(pedido).status_code, 400)
        resposta = views.erro_403(pedido)
        self.assertEqual(resposta.status_code, 403)
        self.assertIn("Acesso negado", resposta.content.decode())

    def test_falha_de_csrf_usa_pagina_propria(self):
        cliente = Client(enforce_csrf_checks=True)
        resposta = cliente.post(reverse("login"), {"username": "x", "password": "y"})
        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, "Sessão expirada", status_code=403)
