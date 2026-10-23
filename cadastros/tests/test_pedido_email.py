from django.core import mail
from django.urls import reverse

from cadastros.models import Order

from .base import CadastrosTestCase


class AvisoNovoPedidoTestCase(CadastrosTestCase):

    def test_pedido_salvo_avisa_os_gerentes_por_email(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=2))

        self.assertEqual(resposta.status_code, 302)
        novo = Order.objects.latest("id")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["gerente@sigep.test"])
        self.assertIn("#{}".format(novo.pk), mail.outbox[0].subject)
        self.assertIn("2 x Produto Teste", mail.outbox[0].body)
        self.assertIn(reverse("order-detail", args=[novo.pk]), mail.outbox[0].body)

    def test_gerente_que_cria_o_pedido_nao_recebe_o_proprio_aviso(self):
        self.entrar(self.gerente)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("order-create"), self.dados_do_pedido())

        self.assertEqual(len(mail.outbox), 0)

    def test_pedido_com_erro_nao_envia_email(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=999))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(resposta.context["itens_iniciais"][0]["quantity"], "999")
