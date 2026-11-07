from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.parse import quote

from django.contrib.auth.models import User
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Client, Company, Order, OrderStatus, PaymentMethod, Product, ProductOrder
from telegram import acoes, comandos, conversa, entradas, recebimento, telas
from telegram.models import ConfiguracaoTelegram, EsperaTelegram, MensagemTelegram, VinculoTelegram

from .base import TELEGRAM_ANA, TELEGRAM_BIA, BotTestCase, clique

TELEGRAM_CAIO = 9_000_000_003
DESCONHECIDO = 9_000_000_099
FOTO = {"photo": [{"file_id": "abc", "file_unique_id": "u", "width": 90, "height": 90}]}


@override_settings(SITE_URL="https://sigep.exemplo.com", TELEGRAM_BOT_USERNAME="sigep_bot")
class SigepBotTestCase(BotTestCase):
    """Ana é gerente das duas empresas; Bia e Caio são representantes só da Boa Vista."""

    def setUp(self):
        super().setUp()
        self.caio = User.objects.create_user("caio", password="x")
        self.boa_vista = self.empresa("Distribuidora Boa Vista", "Boa Vista")
        self.sul = self.empresa("Atacado Sul")
        self.boa_vista.manager.add(self.ana)
        self.boa_vista.sales_rep.add(self.bia, self.caio)
        self.sul.manager.add(self.ana)
        self.papelaria = self.cliente_de(self.boa_vista, "Papelaria Central")
        self.vinculo_ana = self.vincular(self.ana, TELEGRAM_ANA)
        self.vinculo_bia = self.vincular(self.bia, TELEGRAM_BIA)
        self.vinculo_caio = self.vincular(self.caio, TELEGRAM_CAIO)

    def empresa(self, nome, apelido=""):
        return Company.objects.create(name=nome, session_name=apelido, cnpj="00000000000191", created_by=self.ana)

    def cliente_de(self, empresa, nome):
        return Client.objects.create(name=nome, cnpj_cpf="12345678000190", uf="PR", company=empresa, created_by=self.ana)

    def produto_de(self, empresa, nome, sku, estoque, valor="10.00"):
        return Product.objects.create(
            name=nome, sku=sku, stock=estoque, unit_value=Decimal(valor), company=empresa, created_by=self.ana,
        )

    def pedido_de(self, autor, status=OrderStatus.PENDENTE, total="100.00", empresa=None, cliente=None, **campos):
        return Order.objects.create(
            company=empresa or self.boa_vista, client=cliente or self.papelaria, uf="PR", status=status,
            total_value=Decimal(total), created_by=autor, **campos,
        )

    def usar_empresa(self, vinculo, empresa):
        VinculoTelegram.objects.filter(pk=vinculo.pk).update(empresa=empresa)

    def comando(self, texto, telegram_id=TELEGRAM_ANA):
        return self.enviar(texto, telegram_id=telegram_id)

    def tocar(self, data, telegram_id=TELEGRAM_ANA, mensagem_id=99):
        """Toca num botão da mensagem `mensagem_id` e devolve as chamadas que o bot fez à API."""
        antes = len(self.cliente.mensagens)
        atualizacao = clique(data, update_id=self.novo_update_id(), telegram_id=telegram_id)
        atualizacao["callback_query"]["message"]["message_id"] = mensagem_id
        recebimento.receber(atualizacao)
        return self.cliente.mensagens[antes:]

    def botoes(self, mensagem):
        return [botao for linha in mensagem.get("reply_markup", {}).get("inline_keyboard", []) for botao in linha]

    def callbacks(self, mensagem):
        return [botao["callback_data"] for botao in self.botoes(mensagem) if "callback_data" in botao]

    def apagou(self, mensagem_id):
        return {"metodo": "deleteMessage", "chat_id": TELEGRAM_ANA, "message_id": mensagem_id} in self.cliente.mensagens


class MenuTestCase(SimpleTestCase):

    def test_todo_comando_do_menu_e_atendido_e_aparece_na_ajuda(self):
        for nome, descricao in comandos.COMANDOS_DO_MENU:
            with self.subTest(nome=nome):
                self.assertIn("/" + nome, comandos.COMANDOS)
                self.assertIn("/{}: {}".format(nome, descricao), comandos.AJUDA)
                # Regras do setMyCommands
                self.assertRegex(nome, r"^[a-z0-9_]{1,32}$")
                self.assertTrue(3 <= len(descricao) <= 256)

    def test_todo_comando_atendido_esta_no_menu(self):
        # O /start entra pelo botão Iniciar do Telegram, não pelo menu
        no_menu = {"/" + nome for nome, _ in comandos.COMANDOS_DO_MENU}

        self.assertEqual(no_menu, set(comandos.COMANDOS) - {"/start"})


class AjudaTestCase(SigepBotTestCase):

    def test_conectado_recebe_o_que_o_bot_faz_e_os_comandos(self):
        texto = self.comando("/ajuda")["text"]

        self.assertIn(comandos.SOBRE, texto)
        self.assertIn(comandos.AJUDA, texto)

    def test_nao_conectado_recebe_como_conectar(self):
        texto = self.comando("/ajuda", DESCONHECIDO)["text"]

        self.assertIn(comandos.SOBRE, texto)
        self.assertIn(comandos.COMO_CONECTAR, texto)

    def test_consultas_exigem_o_usuario_conectado(self):
        # 4 comandos: abaixo do limite de 5 por minuto de quem não está conectado
        for texto in ("/aprovacoes", "/pedido 1", "/estoque", "/empresa"):
            with self.subTest(texto=texto):
                self.assertEqual(self.comando(texto, DESCONHECIDO)["text"], comandos.COMO_CONECTAR)


class EmpresaDoBotTestCase(SigepBotTestCase):

    def test_com_uma_empresa_so_nao_pergunta(self):
        resposta = self.comando("/aprovacoes", TELEGRAM_BIA)

        self.assertIn("Seus pedidos aguardando aprovação</b> · Boa Vista", resposta["text"])
        self.vinculo_bia.refresh_from_db()
        self.assertEqual(self.vinculo_bia.empresa, self.boa_vista)

    def test_com_varias_empresas_pergunta_com_um_botao_por_empresa(self):
        resposta = self.comando("/aprovacoes")

        self.assertIn("Escolha a empresa", resposta["text"])
        self.assertEqual(self.callbacks(resposta), ["em:{}".format(self.sul.pk), "em:{}".format(self.boa_vista.pk)])
        self.assertEqual([botao["text"] for botao in self.botoes(resposta)], ["Atacado Sul", "Boa Vista"])

    def test_escolher_pelo_botao_grava_e_redesenha_no_lugar(self):
        edicao, resposta_ao_toque = self.tocar("em:{}".format(self.sul.pk))

        self.assertEqual(edicao["metodo"], "editMessageText")
        self.assertEqual((edicao["chat_id"], edicao["message_id"]), (TELEGRAM_ANA, 99))
        self.assertIn("Agora os comandos usam a empresa <b>Atacado Sul</b>", edicao["text"])
        self.assertEqual(resposta_ao_toque["metodo"], "answerCallbackQuery")
        self.vinculo_ana.refresh_from_db()
        self.assertEqual(self.vinculo_ana.empresa, self.sul)

    def test_empresa_de_que_a_pessoa_nao_participa_e_recusada(self):
        chamadas = self.tocar("em:{}".format(self.sul.pk), TELEGRAM_BIA)

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["text"], acoes.SEM_ACESSO_EMPRESA)
        self.assertTrue(chamadas[0]["show_alert"])
        self.vinculo_bia.refresh_from_db()
        self.assertIsNone(self.vinculo_bia.empresa)

    def test_quem_saiu_da_empresa_escolhida_perde_ela_no_bot(self):
        self.usar_empresa(self.vinculo_ana, self.sul)
        self.sul.manager.remove(self.ana)

        # Sobrou só a Boa Vista: ela passa a ser usada sem perguntar
        self.assertIn("Boa Vista", self.comando("/aprovacoes")["text"])

    def test_comando_empresa_marca_a_atual(self):
        self.usar_empresa(self.vinculo_ana, self.sul)

        resposta = self.comando("/empresa")

        self.assertIn("Agora: <b>Atacado Sul</b>", resposta["text"])
        self.assertEqual(self.botoes(resposta)[0]["text"], "✅ Atacado Sul")

    def test_comando_empresa_com_uma_so(self):
        texto = self.comando("/empresa", TELEGRAM_BIA)["text"]

        self.assertIn("Você está só na empresa <b>Boa Vista</b>", texto)

    def test_usuario_sem_empresa(self):
        self.boa_vista.sales_rep.remove(self.bia)

        self.assertEqual(self.comando("/aprovacoes", TELEGRAM_BIA)["text"], telas.SEM_EMPRESA)

    def test_nome_da_empresa_e_escapado(self):
        self.sul.session_name = "<Sul & Cia>"
        self.sul.save()
        self.usar_empresa(self.vinculo_ana, self.sul)

        self.assertIn("Agora: <b>&lt;Sul &amp; Cia&gt;</b>", self.comando("/empresa")["text"])


class AprovacoesTestCase(SigepBotTestCase):

    def setUp(self):
        super().setUp()
        self.usar_empresa(self.vinculo_ana, self.boa_vista)

    def test_gerente_ve_os_pendentes_de_toda_a_empresa(self):
        da_bia = self.pedido_de(self.bia, total="1250.00")
        do_caio = self.pedido_de(self.caio, total="380.00")
        self.pedido_de(self.bia, status=OrderStatus.APROVADO)
        self.pedido_de(self.ana, empresa=self.sul, cliente=self.cliente_de(self.sul, "Cliente Sul"))

        resposta = self.comando("/aprovacoes")

        self.assertIn("Aguardando aprovação</b> · Boa Vista", resposta["text"])
        self.assertIn("2 pedidos · R$ 1.630,00", resposta["text"])
        self.assertIn("#{} · Papelaria Central · R$ 1.250,00".format(da_bia.pk), resposta["text"])
        self.assertEqual(self.callbacks(resposta), ["p:{}:1".format(do_caio.pk), "p:{}:1".format(da_bia.pk)])

    def test_representante_ve_so_os_seus(self):
        meu = self.pedido_de(self.bia)
        self.pedido_de(self.caio)

        resposta = self.comando("/aprovacoes", TELEGRAM_BIA)

        self.assertIn("Seus pedidos aguardando aprovação", resposta["text"])
        self.assertEqual(self.callbacks(resposta), ["p:{}:1".format(meu.pk)])

    def test_sem_pendentes(self):
        self.pedido_de(self.bia, status=OrderStatus.EM_DIGITACAO)

        self.assertIn("Nenhum pedido aguardando aprovação.", self.comando("/aprovacoes")["text"])

    def test_paginas_de_8_com_proxima_e_anterior(self):
        pedidos = [self.pedido_de(self.bia) for _ in range(9)]

        resposta = self.comando("/aprovacoes")

        self.assertEqual(len(self.callbacks(resposta)), 9)  # 8 pedidos + Próxima
        self.assertEqual(self.callbacks(resposta)[-1], "ap:2")
        self.assertIn("Página 1 de 2", resposta["text"])

        segunda = self.tocar("ap:2")[0]
        self.assertEqual(self.callbacks(segunda), ["p:{}:2".format(pedidos[0].pk), "ap:1"])
        self.assertIn("Página 2 de 2", segunda["text"])

    def test_tocar_no_pedido_abre_o_cartao_com_voltar(self):
        pedido = self.pedido_de(self.bia)

        cartao = self.tocar("p:{}:2".format(pedido.pk))[0]

        self.assertEqual(cartao["metodo"], "editMessageText")
        self.assertIn("Pedido nº {}".format(pedido.pk), cartao["text"])
        self.assertEqual(self.callbacks(cartao), ["ap:2"])

    def test_nome_do_cliente_e_escapado(self):
        self.papelaria.name = "<b>Papelaria</b> & Cia"
        self.papelaria.save()
        self.pedido_de(self.bia)

        texto = self.comando("/aprovacoes")["text"]

        self.assertIn("&lt;b&gt;Papelaria&lt;/b&gt; &amp; Cia", texto)


class PedidoTestCase(SigepBotTestCase):

    def setUp(self):
        super().setUp()
        self.usar_empresa(self.vinculo_ana, self.boa_vista)
        self.caderno = self.produto_de(self.boa_vista, "Caderno 96 fls", "CAD-096", 50, "19.90")
        self.pedido = self.pedido_de(
            self.bia, total="199.00", payment_method=PaymentMethod.BOLETO, installments=3,
        )
        self.item(10, "199.00")

    def item(self, quantidade, total):
        ProductOrder.objects.create(
            order=self.pedido, product=self.caderno, quantity=quantidade,
            unit_value=Decimal("19.90"), total_value=Decimal(total),
        )

    def test_cartao_do_pedido(self):
        texto = self.comando("/pedido {}".format(self.pedido.pk))["text"]

        for trecho in (
            "Pedido nº {}</b> · Pendente".format(self.pedido.pk), "🏢 Boa Vista",
            "Cliente: Papelaria Central (12.345.678/0001-90)", "Criado por: bia em ",
            "Pagamento: Boleto(30) em 3x", "Itens (1):", "• 10 × Caderno 96 fls = R$ 199,00", "Total: <b>R$ 199,00</b>",
        ):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, texto)

    def test_cartao_nao_tem_botao_que_muda_o_status(self):
        resposta = self.comando("/pedido {}".format(self.pedido.pk))

        self.assertEqual(self.callbacks(resposta), [])
        self.assertEqual([botao["text"] for botao in self.botoes(resposta)], ["🌐 Abrir no site"])

    def test_aceita_cerquilha_e_o_nome_do_bot(self):
        self.assertIn("Pedido nº", self.comando("/pedido@sigep_bot #{}".format(self.pedido.pk))["text"])

    def test_comando_para_outro_bot_nao_e_atendido(self):
        self.assertEqual(self.comando("/pedido@outro_bot {}".format(self.pedido.pk))["text"], comandos.AJUDA)

    def test_representante_nao_ve_o_pedido_de_outro(self):
        do_caio = self.pedido_de(self.caio)

        texto = self.comando("/pedido {}".format(do_caio.pk), TELEGRAM_BIA)["text"]

        self.assertIn("Não encontrei o pedido nº {}".format(do_caio.pk), texto)

    def test_pedido_de_outra_empresa_nao_aparece(self):
        da_sul = self.pedido_de(self.ana, empresa=self.sul, cliente=self.cliente_de(self.sul, "Cliente Sul"))

        self.assertIn("Não encontrei", self.comando("/pedido {}".format(da_sul.pk))["text"])

    def test_numero_invalido_recebe_a_dica(self):
        self.assertEqual(self.comando("/pedido abc")["text"], entradas.DICA_NUMERO)

    def test_abrir_no_site_ativa_a_empresa_do_bot_antes(self):
        url = self.botoes(self.comando("/pedido {}".format(self.pedido.pk)))[0]["url"]

        self.assertEqual(url, "https://sigep.exemplo.com{}?next={}".format(
            reverse("activate-company", args=[self.boa_vista.pk]), quote(reverse("order-detail", args=[self.pedido.pk])),
        ))

    @override_settings(SITE_URL="http://127.0.0.1:8000")
    def test_sem_https_o_cartao_vai_sem_botao(self):
        self.assertNotIn("reply_markup", self.comando("/pedido {}".format(self.pedido.pk)))

    def test_muitos_itens_mostra_os_10_primeiros(self):
        for _ in range(11):
            self.item(1, "19.90")

        texto = self.comando("/pedido {}".format(self.pedido.pk))["text"]

        self.assertIn("Itens (12):", texto)
        self.assertIn("… e mais 2 itens", texto)

    def test_pelo_botao_o_representante_nao_abre_o_pedido_de_outro(self):
        do_caio = self.pedido_de(self.caio)

        chamadas = self.tocar("p:{}:1".format(do_caio.pk), TELEGRAM_BIA)

        self.assertEqual([chamada["metodo"] for chamada in chamadas], ["answerCallbackQuery"])
        self.assertTrue(chamadas[0]["show_alert"])
        self.assertIn("Não encontrei", chamadas[0]["text"])

    def test_sem_numero_pergunta_e_a_resposta_mostra_o_cartao_no_fim(self):
        pergunta = self.comando("/pedido")
        espera = EsperaTelegram.objects.get()

        self.assertEqual(pergunta["text"], conversa.CAMPOS_TEXTO["pedido"].pergunta)
        self.assertEqual(self.callbacks(pergunta), ["cx"])
        self.assertEqual(espera.campo, "pedido")

        antes = len(self.cliente.mensagens)
        self.comando("#{}".format(self.pedido.pk))
        apagada, cartao = self.cliente.mensagens[antes:]

        self.assertEqual(apagada, {"metodo": "deleteMessage", "chat_id": TELEGRAM_ANA, "message_id": espera.mensagem_pergunta_id})
        self.assertIn("Pedido nº {}".format(self.pedido.pk), cartao["text"])
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_resposta_que_nao_e_numero_recebe_a_dica_e_continua_esperando(self):
        self.comando("/pedido")

        self.assertEqual(self.comando("ontem")["text"], entradas.DICA_NUMERO)
        self.assertTrue(EsperaTelegram.objects.exists())

    def test_pedido_que_nao_existe_continua_esperando(self):
        self.comando("/pedido")

        self.assertIn("Não encontrei o pedido nº 999999", self.comando("999999")["text"])
        self.assertTrue(EsperaTelegram.objects.exists())

    def test_sem_empresa_escolhida_pergunta_a_empresa_antes_do_numero(self):
        self.usar_empresa(self.vinculo_ana, None)

        self.assertIn("Escolha a empresa", self.comando("/pedido")["text"])
        self.assertFalse(EsperaTelegram.objects.exists())


class EstoqueTestCase(SigepBotTestCase):

    def setUp(self):
        super().setUp()
        self.usar_empresa(self.vinculo_ana, self.boa_vista)
        self.caderno = self.produto_de(self.boa_vista, "Caderno 96 fls", "CAD-096", 3, "19.90")
        self.caneta = self.produto_de(self.boa_vista, "Caneta azul", "CAN-AZ", 200, "2.50")
        self.da_sul = self.produto_de(self.sul, "Caderno da Sul", "CAD-SUL", 0)

    def test_sem_termo_mostra_o_estoque_baixo_da_empresa(self):
        resposta = self.comando("/estoque")

        self.assertIn("Estoque baixo</b> (até 10 unidades) · Boa Vista", resposta["text"])
        self.assertIn("<code>CAD-096</code> · Caderno 96 fls · 3 UND ⚠️ · R$ 19,90", resposta["text"])
        self.assertNotIn("Caneta", resposta["text"])
        self.assertNotIn("Sul", resposta["text"])
        self.assertEqual(self.callbacks(resposta), ["pr:{}:1:".format(self.caderno.pk), "bp"])

    def test_busca_pelo_nome_ou_pelo_sku(self):
        self.assertIn("Caneta azul", self.comando("/estoque caneta")["text"])
        self.assertIn("Caneta azul", self.comando("/estoque can-az")["text"])

        texto = self.comando("/estoque caderno")["text"]
        self.assertIn("1 produto\n", texto)
        self.assertNotIn("Sul", texto)

    def test_termo_curto_recebe_a_dica(self):
        self.assertEqual(self.comando("/estoque a")["text"], entradas.DICA_TERMO)

    def test_nada_encontrado(self):
        self.assertIn("Nenhum produto encontrado.", self.comando("/estoque grampeador")["text"])

    def test_termo_da_busca_e_escapado(self):
        self.assertIn('com "&lt;ca&gt;"', self.comando("/estoque <ca>")["text"])

    def test_cartao_do_produto_e_voltar_para_a_busca(self):
        cartao = self.tocar("pr:{}:1:cad".format(self.caderno.pk))[0]

        self.assertIn("📦 <b>Caderno 96 fls</b>", cartao["text"])
        self.assertIn("Estoque: 3 · [UND] Unidade ⚠️ estoque baixo", cartao["text"])
        self.assertEqual(self.callbacks(cartao), ["es:1:cad"])

        lista = self.tocar("es:1:cad")[0]
        self.assertIn('Produtos com "cad"', lista["text"])

    def test_produto_de_outra_empresa_pelo_botao_e_recusado(self):
        chamadas = self.tocar("pr:{}:1:".format(self.da_sul.pk))

        self.assertEqual([chamada["metodo"] for chamada in chamadas], ["answerCallbackQuery"])
        self.assertTrue(chamadas[0]["show_alert"])

    def test_termo_longo_cabe_nos_botoes(self):
        # Pior caso: 30 caracteres, quase todos de 4 bytes (114 bytes), bem acima dos 64 do callback_data
        termo = "ab" + "📦" * 28
        self.produto_de(self.boa_vista, "Produto " + termo, "LONGO", 5)

        resposta = self.comando("/estoque " + termo)

        self.assertIn("1 produto", resposta["text"])
        for dado in self.callbacks(resposta):
            self.assertLessEqual(len(dado.encode("utf-8")), 64)

    def test_buscar_produto_vira_pergunta_e_a_resposta_vai_para_o_fim(self):
        pergunta, resposta_ao_toque = self.tocar("bp")

        self.assertEqual((pergunta["metodo"], pergunta["message_id"]), ("editMessageText", 99))
        self.assertEqual(pergunta["text"], conversa.CAMPOS_TEXTO["busca"].pergunta)
        self.assertEqual(resposta_ao_toque["metodo"], "answerCallbackQuery")

        antes = len(self.cliente.mensagens)
        self.comando("caneta")
        apagada, lista = self.cliente.mensagens[antes:]

        self.assertEqual(apagada, {"metodo": "deleteMessage", "chat_id": TELEGRAM_ANA, "message_id": 99})
        self.assertIn("Caneta azul", lista["text"])


class DespachoTestCase(SigepBotTestCase):

    def metodos(self, chamadas):
        return [chamada["metodo"] for chamada in chamadas]

    def test_botao_desconhecido_e_antigo(self):
        chamadas = self.tocar("zz:1")

        self.assertEqual(self.metodos(chamadas), ["answerCallbackQuery"])
        self.assertEqual(chamadas[0]["text"], acoes.BOTAO_ANTIGO)
        self.assertTrue(chamadas[0]["show_alert"])

    def test_argumento_adulterado_e_recusado_sem_erro(self):
        for dado in ("p:abc", "ap:", "pr:1:x:", "em:-", "p:1:zz"):
            with self.subTest(dado=dado):
                chamadas = self.tocar(dado)
                self.assertEqual(self.metodos(chamadas), ["answerCallbackQuery"])
                self.assertEqual(chamadas[0]["text"], acoes.BOTAO_ANTIGO)
        self.assertFalse(MensagemTelegram.objects.filter(situacao=MensagemTelegram.Situacao.ERRO).exists())

    def test_sem_vinculo_o_botao_e_antigo(self):
        chamadas = self.tocar("ap:1", DESCONHECIDO)

        self.assertEqual(self.metodos(chamadas), ["answerCallbackQuery"])
        self.assertEqual(chamadas[0]["text"], acoes.BOTAO_ANTIGO)

    def test_toque_que_da_certo_e_respondido_uma_vez(self):
        self.assertEqual(self.metodos(self.tocar("ap:1")).count("answerCallbackQuery"), 1)

    def test_toque_que_quebra_e_respondido_uma_vez_e_vira_aviso_de_erro(self):
        with self.assertLogs("telegram.recebimento", level="ERROR"):
            with mock.patch.dict(acoes.ACOES, {"ap": mock.Mock(side_effect=RuntimeError("quebrou"))}):
                chamadas = self.tocar("ap:1")

        self.assertEqual(self.metodos(chamadas).count("answerCallbackQuery"), 1)
        self.assertEqual(chamadas[-1]["text"], recebimento.ERRO_GENERICO)

    def test_se_nao_der_para_editar_manda_mensagem_nova(self):
        self.cliente.programar("editMessageText", None)

        self.assertEqual(self.metodos(self.tocar("ap:1")), ["editMessageText", "sendMessage", "answerCallbackQuery"])


class EsperaTestCase(SigepBotTestCase):

    def setUp(self):
        super().setUp()
        self.usar_empresa(self.vinculo_ana, self.boa_vista)
        self.vinculo_ana.refresh_from_db()

    def pedir(self, campo="pedido"):
        conversa.pedir(self.vinculo_ana, campo, TELEGRAM_ANA)
        return EsperaTelegram.objects.get()

    def envelhecer(self, **tempo):
        EsperaTelegram.objects.update(desde=timezone.now() - timedelta(**tempo))

    def test_pedir_cria_a_espera_com_a_pergunta_e_o_cancelar(self):
        espera = self.pedir()
        pergunta = self.cliente.mensagens[-1]

        self.assertEqual(espera.campo, "pedido")
        self.assertIsNotNone(espera.mensagem_pergunta_id)
        self.assertEqual(pergunta["text"], conversa.CAMPOS_TEXTO["pedido"].pergunta)
        self.assertEqual(self.callbacks(pergunta), ["cx"])

    def test_nova_pergunta_substitui_a_anterior_e_apaga_a_velha(self):
        primeira = self.pedir("pedido")

        segunda = self.pedir("busca")

        self.assertEqual(EsperaTelegram.objects.count(), 1)
        self.assertEqual(segunda.campo, "busca")
        self.assertNotEqual(segunda.mensagem_pergunta_id, primeira.mensagem_pergunta_id)
        self.assertTrue(self.apagou(primeira.mensagem_pergunta_id))
        self.assertGreaterEqual(segunda.desde, primeira.desde)

    def test_espera_vence_em_15_minutos(self):
        self.pedir()
        self.envelhecer(minutes=15, seconds=1)

        self.assertEqual(self.comando("128")["text"], comandos.AJUDA)
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_espera_dentro_do_prazo_vale(self):
        pedido = self.pedido_de(self.bia)
        self.pedir()
        self.envelhecer(minutes=14)

        self.assertIn("Pedido nº {}".format(pedido.pk), self.comando(str(pedido.pk))["text"])

    def test_prazo_vem_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.espera_minutos = 2
        config.save()
        self.pedir()
        self.envelhecer(minutes=3)

        self.assertEqual(self.comando("128")["text"], comandos.AJUDA)

    def test_cancelar_pelo_comando_apaga_a_pergunta(self):
        espera = self.pedir()

        self.assertEqual(self.comando("/cancelar")["text"], comandos.CANCELADO)
        self.assertTrue(self.apagou(espera.mensagem_pergunta_id))
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_outro_comando_cancela_a_espera(self):
        espera = self.pedir()

        self.comando("/aprovacoes")

        self.assertFalse(EsperaTelegram.objects.exists())
        self.assertTrue(self.apagou(espera.mensagem_pergunta_id))

    def test_foto_cancela_a_espera(self):
        self.pedir()

        self.enviar(telegram_id=TELEGRAM_ANA, **FOTO)

        self.assertFalse(EsperaTelegram.objects.exists())

    def test_cancelar_pelo_botao_redesenha_a_pergunta(self):
        espera = self.pedir()

        edicao, resposta_ao_toque = self.tocar("cx", mensagem_id=espera.mensagem_pergunta_id)

        self.assertEqual((edicao["metodo"], edicao["text"]), ("editMessageText", conversa.PERGUNTA_CANCELADA))
        self.assertEqual(resposta_ao_toque["metodo"], "answerCallbackQuery")
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_cancelar_de_uma_pergunta_velha_e_botao_antigo(self):
        self.pedir()

        chamadas = self.tocar("cx", mensagem_id=12345)

        self.assertEqual(chamadas[0]["text"], acoes.BOTAO_ANTIGO)
        self.assertTrue(EsperaTelegram.objects.exists())

    def test_espera_de_outra_pessoa_nao_e_cancelada_pelo_botao(self):
        espera = self.pedir()

        chamadas = self.tocar("cx", TELEGRAM_BIA, mensagem_id=espera.mensagem_pergunta_id)

        self.assertEqual(chamadas[0]["text"], acoes.BOTAO_ANTIGO)
        self.assertTrue(EsperaTelegram.objects.exists())
