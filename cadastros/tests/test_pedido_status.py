from decimal import Decimal

from django.contrib.messages import get_messages
from django.core import mail
from django.urls import reverse

from cadastros.models import Order, OrderStatus

from .base import CadastrosTestCase


class StatusPedidoTestCase(CadastrosTestCase):
    """Ciclo de vida do pedido e estoque (RF11, RF14, RN03, RN05, RN08, RN09)."""

    def mudar_status(self, pedido, status):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("order-status", args=[pedido.pk]), {"status": status})

    def estoque(self):
        self.produto.refresh_from_db()
        return self.produto.stock

    def status_de(self, pedido):
        pedido.refresh_from_db()
        return pedido.status

    def mensagens(self, resposta):
        # Todas as mensagens pendentes, inclusive as de requisições anteriores sem redirect seguido
        return " ".join(str(mensagem) for mensagem in get_messages(resposta.wsgi_request))

    # Botões do formulário
    def test_salvar_em_rascunho_nao_baixa_estoque_nem_avisa(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=3, acao="rascunho"))

        pedido = Order.objects.get()
        self.assertRedirects(resposta, reverse("order-detail", args=[pedido.pk]), fetch_redirect_response=False)
        self.assertEqual(pedido.status, OrderStatus.EM_DIGITACAO)
        self.assertEqual(pedido.product_orders.count(), 1)
        self.assertEqual(self.estoque(), 10)
        self.assertEqual(len(mail.outbox), 0)

    def test_sem_acao_salva_em_rascunho(self):
        dados = self.dados_do_pedido()
        del dados["acao"]
        self.entrar(self.rep1)
        self.client.post(reverse("order-create"), dados)

        self.assertEqual(Order.objects.get().status, OrderStatus.EM_DIGITACAO)
        self.assertEqual(self.estoque(), 10)

    def test_salvar_e_enviar_deixa_pendente_baixa_estoque_e_avisa(self):
        self.entrar(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=3, acao="enviar"))

        self.assertEqual(Order.objects.get().status, OrderStatus.PENDENTE)
        self.assertEqual(self.estoque(), 7)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("aguardando aprovação", mail.outbox[0].subject)

    def test_rascunho_aceita_quantidade_acima_do_estoque_mas_o_envio_nao(self):
        self.entrar(self.rep1)
        self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=15, acao="rascunho"))
        rascunho = Order.objects.get()
        self.assertEqual(rascunho.status, OrderStatus.EM_DIGITACAO)

        resposta = self.mudar_status(rascunho, OrderStatus.PENDENTE)

        self.assertEqual(self.status_de(rascunho), OrderStatus.EM_DIGITACAO)
        self.assertEqual(self.estoque(), 10)
        self.assertIn("Estoque insuficiente para 'Produto Teste': disponível 10, solicitado 15.", self.mensagens(resposta))
        self.assertEqual(len(mail.outbox), 0)

    # Edição e exclusão (só rascunho)
    def test_rascunho_e_editado_com_os_itens(self):
        rascunho = self.criar_pedido(self.rep1, 2, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)
        url = reverse("order-update", args=[rascunho.pk])

        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.context["itens_iniciais"],
            [{"product_id": self.produto.pk, "quantity": 2, "discount": Decimal("0")}],
        )

        self.client.post(url, self.dados_do_pedido(quantidade=4, acao="rascunho"))
        rascunho.refresh_from_db()
        self.assertEqual(rascunho.status, OrderStatus.EM_DIGITACAO)
        self.assertEqual(rascunho.total_value, Decimal("40.00"))
        self.assertEqual([item.quantity for item in rascunho.product_orders.all()], [4])
        self.assertEqual(self.estoque(), 10)

    def test_editar_rascunho_e_enviar(self):
        rascunho = self.criar_pedido(self.rep1, 2, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)
        self.client.post(reverse("order-update", args=[rascunho.pk]), self.dados_do_pedido(quantidade=4))

        self.assertEqual(self.status_de(rascunho), OrderStatus.PENDENTE)
        self.assertEqual(self.estoque(), 6)

    def test_pedido_enviado_nao_e_editado_nem_excluido(self):
        pendente = self.criar_pedido(self.rep1, 2, status=OrderStatus.PENDENTE)
        self.entrar(self.rep1)
        url = reverse("order-update", args=[pendente.pk])

        resposta = self.client.get(url)
        self.assertRedirects(resposta, reverse("order-detail", args=[pendente.pk]), fetch_redirect_response=False)
        self.client.post(url, self.dados_do_pedido(quantidade=9, acao="rascunho"))
        self.assertEqual(pendente.product_orders.get().quantity, 2)

        resposta = self.client.post(reverse("order-delete", args=[pendente.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Order.objects.filter(pk=pendente.pk).exists())

    def test_rascunho_pode_ser_excluido(self):
        rascunho = self.criar_pedido(self.rep1, 2, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)
        self.client.post(reverse("order-delete", args=[rascunho.pk]))

        self.assertFalse(Order.objects.filter(pk=rascunho.pk).exists())

    # Representante
    def test_representante_envia_e_cancela_o_pendente_com_estorno(self):
        rascunho = self.criar_pedido(self.rep1, 3, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)

        self.mudar_status(rascunho, OrderStatus.PENDENTE)
        self.assertEqual(self.status_de(rascunho), OrderStatus.PENDENTE)
        self.assertEqual(self.estoque(), 7)
        self.assertEqual(mail.outbox[0].to, ["gerente@sigep.test"])

        self.mudar_status(rascunho, OrderStatus.CANCELADO)
        self.assertEqual(self.status_de(rascunho), OrderStatus.CANCELADO)
        self.assertEqual(self.estoque(), 10)

    def test_representante_nao_aprova_nem_rejeita(self):
        pendente = self.criar_pedido(self.rep1, 3, status=OrderStatus.PENDENTE)
        self.entrar(self.rep1)

        for status in (OrderStatus.APROVADO, OrderStatus.REJEITADO):
            with self.subTest(status=status):
                resposta = self.mudar_status(pendente, status)
                self.assertEqual(self.status_de(pendente), OrderStatus.PENDENTE)
                self.assertIn("Você não pode mudar", self.mensagens(resposta))
        self.assertEqual(self.estoque(), 10)

    def test_representante_nao_cancela_pedido_aprovado(self):
        aprovado = self.criar_pedido(self.rep1, 3, status=OrderStatus.APROVADO)
        self.entrar(self.rep1)
        self.mudar_status(aprovado, OrderStatus.CANCELADO)

        self.assertEqual(self.status_de(aprovado), OrderStatus.APROVADO)

    def test_representante_nao_muda_status_de_pedido_de_outro(self):
        alheio = self.criar_pedido(self.rep2, 1, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)

        self.assertEqual(self.mudar_status(alheio, OrderStatus.PENDENTE).status_code, 404)
        self.assertEqual(self.status_de(alheio), OrderStatus.EM_DIGITACAO)

    def test_enviar_duas_vezes_nao_baixa_o_estoque_em_dobro(self):
        rascunho = self.criar_pedido(self.rep1, 3, status=OrderStatus.EM_DIGITACAO)
        self.entrar(self.rep1)
        self.mudar_status(rascunho, OrderStatus.PENDENTE)
        self.mudar_status(rascunho, OrderStatus.PENDENTE)

        self.assertEqual(self.estoque(), 7)

    # Gerente
    def test_gerente_muda_para_qualquer_status_e_o_estoque_acompanha(self):
        self.entrar(self.rep1)
        self.client.post(reverse("order-create"), self.dados_do_pedido(quantidade=4))
        pedido = Order.objects.get()
        self.assertEqual(self.estoque(), 6)

        self.entrar(self.gerente)
        passos = [
            (OrderStatus.APROVADO, 6),      # aprovar não mexe: já estava baixado
            (OrderStatus.REJEITADO, 10),    # rejeitar devolve
            (OrderStatus.APROVADO, 6),      # reaprovar baixa de novo
            (OrderStatus.CANCELADO, 10),    # cancelar aprovado devolve (RN09)
            (OrderStatus.EM_DIGITACAO, 10), # volta para digitação sem baixar
            (OrderStatus.PENDENTE, 6),      # reenviar baixa
        ]
        for status, estoque in passos:
            with self.subTest(status=status):
                self.mudar_status(pedido, status)
                self.assertEqual(self.status_de(pedido), status)
                self.assertEqual(self.estoque(), estoque)

    def test_tela_mostra_so_as_acoes_permitidas(self):
        pendente = self.criar_pedido(self.rep1, 1, status=OrderStatus.PENDENTE)
        url = reverse("order-detail", args=[pendente.pk])

        self.entrar(self.rep1)
        acoes = self.client.get(url).context["acoes_status"]
        self.assertEqual([acao["status"] for acao in acoes], [OrderStatus.CANCELADO])

        self.entrar(self.gerente)
        acoes = self.client.get(url).context["acoes_status"]
        self.assertCountEqual(
            [acao["status"] for acao in acoes],
            [OrderStatus.EM_DIGITACAO, OrderStatus.APROVADO, OrderStatus.REJEITADO, OrderStatus.CANCELADO],
        )

    # Vendas
    def test_painel_conta_so_pedidos_aprovados(self):
        for quantidade, status in enumerate(OrderStatus.values, start=1):
            self.criar_pedido(self.rep1, quantidade, status=status)
        aprovado = OrderStatus.values.index(OrderStatus.APROVADO) + 1

        self.entrar(self.gerente)
        resposta = self.client.get(reverse("index"))

        self.assertEqual(resposta.context["qtd_vendas"], 1)
        self.assertEqual(resposta.context["total_vendas"], self.produto.unit_value * aprovado)
        self.assertEqual(len(resposta.context["ultimos_pedidos"]), len(OrderStatus.values))
