from django.core import mail
from django.urls import reverse

from cadastros.models import MAX_PARCELAS, Order, OrderStatus, PaymentMethod

from .base import CadastrosTestCase


class ParcelasPedidoTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.entrar(self.rep1)

    def dados(self, metodo, parcelas=None, acao="rascunho"):
        dados = self.dados_do_pedido(acao=acao)
        dados["payment_method"] = metodo
        if parcelas is not None:
            dados["installments"] = parcelas
        return dados

    def salvar(self, metodo, parcelas=None):
        return self.client.post(reverse("order-create"), self.dados(metodo, parcelas))

    def test_todos_os_boletos_gravam_as_parcelas(self):
        for metodo in (PaymentMethod.BOLETO, PaymentMethod.BOLETO15, PaymentMethod.BOLETO7):
            with self.subTest(metodo=metodo):
                self.salvar(metodo, "3")
                self.assertEqual(Order.objects.latest("id").installments, 3)

    def test_fora_do_boleto_vale_sempre_uma_parcela(self):
        # Inclui valor fora do limite e texto: o campo fica escondido e não pode travar o pedido
        for parcelas in (None, "", "5", "99", "abc"):
            with self.subTest(parcelas=parcelas):
                resposta = self.salvar(PaymentMethod.PIX, parcelas)
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(Order.objects.latest("id").installments, 1)

    def test_boleto_exige_as_parcelas_dentro_do_limite(self):
        for parcelas in ("", "0", str(MAX_PARCELAS + 1)):
            with self.subTest(parcelas=parcelas):
                resposta = self.salvar(PaymentMethod.BOLETO, parcelas)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn("installments", resposta.context["form"].errors)
        self.assertFalse(Order.objects.exists())

    def test_limite_maximo_e_aceito(self):
        self.salvar(PaymentMethod.BOLETO, str(MAX_PARCELAS))

        self.assertEqual(Order.objects.get().installments, MAX_PARCELAS)

    def test_formulario_comeca_com_uma_parcela_e_informa_os_metodos(self):
        resposta = self.client.get(reverse("order-create"))

        self.assertEqual(resposta.context["form"]["installments"].value(), 1)
        self.assertContains(resposta, 'data-metodos-boleto="boleto 30dias,boleto 15dias,boleto 7dias"')

    def test_endereco_cidade_e_uf_ficam_na_mesma_linha(self):
        html = self.client.get(reverse("order-create")).content.decode()
        colunas = (
            r'class="col-12 col-md-7"\s*>\s*<div id="div_id_address".*?'
            r'class="col-12 col-md-3"\s*>\s*<div id="div_id_city".*?'
            r'class="col-12 col-md-2"\s*>\s*<div id="div_id_uf"'
        )

        self.assertRegex(html.replace("\n", " "), colunas)

    def test_erro_de_itens_mantem_as_parcelas_digitadas(self):
        dados = self.dados(PaymentMethod.BOLETO, "4")
        dados["quantity[]"] = ["0"]
        resposta = self.client.post(reverse("order-create"), dados)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["form"]["installments"].value(), "4")

    def test_duplicar_leva_as_parcelas(self):
        original = self.criar_pedido(self.rep1, 1)
        Order.objects.filter(pk=original.pk).update(payment_method=PaymentMethod.BOLETO, installments=6)
        resposta = self.client.get(reverse("order-duplicate", args=[original.pk]))

        self.assertEqual(resposta.context["form"].initial["installments"], 6)

    def test_rascunho_que_deixa_de_ser_boleto_volta_para_uma_parcela(self):
        rascunho = self.criar_pedido(self.rep1, 1, status=OrderStatus.EM_DIGITACAO)
        Order.objects.filter(pk=rascunho.pk).update(payment_method=PaymentMethod.BOLETO, installments=6)
        self.client.post(reverse("order-update", args=[rascunho.pk]), self.dados(PaymentMethod.PIX, "6"))

        rascunho.refresh_from_db()
        self.assertEqual(rascunho.payment_method, PaymentMethod.PIX)
        self.assertEqual(rascunho.installments, 1)

    def test_detalhe_mostra_as_parcelas_so_no_boleto(self):
        pedido = self.criar_pedido(self.rep1, 1)
        url = reverse("order-detail", args=[pedido.pk])
        self.assertNotContains(self.client.get(url), "<th>Parcelas</th>")

        Order.objects.filter(pk=pedido.pk).update(payment_method=PaymentMethod.BOLETO, installments=3)
        resposta = self.client.get(url)
        self.assertContains(resposta, "<th>Parcelas</th>")
        self.assertContains(resposta, "<td>3x</td>")

    def test_email_aos_gerentes_informa_as_parcelas(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("order-create"), self.dados(PaymentMethod.BOLETO, "3", acao="enviar"))

        self.assertIn("Boleto(30) em 3x", mail.outbox[0].body)
