from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cadastros.models import User_Profile
from telegram import comandos, recebimento, services
from telegram.cliente import obter_cliente
from telegram.models import CodigoVinculoTelegram, EsperaTelegram, MensagemTelegram, VinculoTelegram
from telegram.views import CHAVE_SESSAO_CODIGO

from .base import TELEGRAM_ANA, TELEGRAM_BIA, BotTestCase, update

SEGREDO = "segredo-do-webhook"


@override_settings(SITE_URL="https://sigep.exemplo.com")
class StartComCodigoTestCase(BotTestCase):

    def test_codigo_valido_cria_o_vinculo_com_os_dados_do_telegram(self):
        resposta = self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.ana)))

        vinculo = VinculoTelegram.objects.get()
        self.assertEqual(vinculo.usuario, self.ana)
        self.assertEqual(vinculo.telegram_id, TELEGRAM_ANA)
        self.assertEqual(vinculo.chat_id, TELEGRAM_ANA)
        self.assertEqual(vinculo.username, "ana_tg")
        self.assertEqual(vinculo.nome, "Ana Souza")
        self.assertIsNotNone(CodigoVinculoTelegram.objects.get().usado_em)
        self.assertIn("✅ Conectado como ana", resposta["text"])
        self.assertIn(comandos.AJUDA, resposta["text"])

    def test_codigo_vale_uma_vez(self):
        token = CodigoVinculoTelegram.emitir(self.ana)
        self.enviar("/start {}".format(token))

        resposta = self.enviar("/start {}".format(token), telegram_id=TELEGRAM_BIA)

        self.assertEqual(resposta["text"], comandos.CODIGO_INVALIDO)
        self.assertEqual(VinculoTelegram.objects.get().telegram_id, TELEGRAM_ANA)

    def test_uso_simultaneo_so_uma_das_mensagens_conecta(self):
        token = CodigoVinculoTelegram.emitir(self.ana)
        codigo = CodigoVinculoTelegram.buscar_valido(token)
        # A outra mensagem marcou o código depois do buscar_valido desta
        CodigoVinculoTelegram.objects.update(usado_em=timezone.now())

        with mock.patch.object(CodigoVinculoTelegram, "buscar_valido", return_value=codigo):
            self.assertIsNone(services.conectar(token, TELEGRAM_ANA, TELEGRAM_ANA))

        self.assertFalse(VinculoTelegram.objects.exists())

    def test_codigo_vencido_nao_conecta(self):
        token = CodigoVinculoTelegram.emitir(self.ana)
        CodigoVinculoTelegram.objects.update(expira_em=timezone.now() - timedelta(seconds=1))

        resposta = self.enviar("/start {}".format(token))

        self.assertEqual(resposta["text"], comandos.CODIGO_INVALIDO)
        self.assertFalse(VinculoTelegram.objects.exists())

    def test_codigo_novo_invalida_o_anterior(self):
        anterior = CodigoVinculoTelegram.emitir(self.ana)
        novo = CodigoVinculoTelegram.emitir(self.ana)

        self.assertEqual(self.enviar("/start {}".format(anterior))["text"], comandos.CODIGO_INVALIDO)
        self.assertFalse(VinculoTelegram.objects.exists())

        self.assertIn("✅ Conectado", self.enviar("/start {}".format(novo))["text"])
        self.assertTrue(VinculoTelegram.objects.filter(usuario=self.ana).exists())

    def test_codigo_invalido_mostra_botao_para_a_tela(self):
        resposta = self.enviar("/start nao-existe")

        self.assertEqual(
            resposta["reply_markup"]["inline_keyboard"][0][0]["url"],
            "https://sigep.exemplo.com" + reverse("telegram:conexao"),
        )

    @override_settings(SITE_URL="http://127.0.0.1:8000")
    def test_sem_https_responde_sem_o_botao(self):
        resposta = self.enviar("/start nao-existe")

        self.assertEqual(resposta["text"], comandos.CODIGO_INVALIDO)
        self.assertNotIn("reply_markup", resposta)

    def test_telegram_ligado_a_outro_usuario_troca_de_usuario(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.bia)))

        vinculo = VinculoTelegram.objects.get()
        self.assertEqual(vinculo.usuario, self.bia)
        self.assertEqual(vinculo.telegram_id, TELEGRAM_ANA)

    def test_usuario_ligado_a_outro_telegram_troca_de_telegram(self):
        self.vincular(self.ana, TELEGRAM_BIA)

        self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.ana)))

        self.assertEqual(VinculoTelegram.objects.get().telegram_id, TELEGRAM_ANA)

    def test_troca_com_os_dois_lados_ja_ligados(self):
        # Ana no Telegram 1, Bia no Telegram 2; Bia conecta pelo Telegram 1
        self.vincular(self.ana, TELEGRAM_ANA)
        self.vincular(self.bia, TELEGRAM_BIA)

        self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.bia)))

        vinculo = VinculoTelegram.objects.get()
        self.assertEqual(vinculo.usuario, self.bia)
        self.assertEqual(vinculo.telegram_id, TELEGRAM_ANA)

    def test_troca_atualiza_a_data_e_descarta_a_pergunta_pendente(self):
        antigo = self.vincular(self.ana, TELEGRAM_ANA)
        VinculoTelegram.objects.filter(pk=antigo.pk).update(vinculado_em=timezone.now() - timedelta(days=30))
        EsperaTelegram.objects.create(vinculo=antigo, campo="data")

        self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.bia)))

        self.assertGreater(VinculoTelegram.objects.get().vinculado_em, timezone.now() - timedelta(minutes=1))
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_usuario_desativado_nao_conecta_com_codigo_antigo(self):
        token = CodigoVinculoTelegram.emitir(self.ana)
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

        resposta = self.enviar("/start {}".format(token))

        self.assertEqual(resposta["text"], comandos.CODIGO_INVALIDO)
        self.assertFalse(VinculoTelegram.objects.exists())

    def test_primeiro_nome_vem_do_perfil_e_e_escapado(self):
        User_Profile.objects.create(user=self.ana, name="<Maria> da Silva", phone="41999999999", cpf="52998224725")

        resposta = self.enviar("/start {}".format(CodigoVinculoTelegram.emitir(self.ana)))

        self.assertIn("Conectado como &lt;Maria&gt;\n", resposta["text"])

    def test_pessoa_sem_username_nem_sobrenome(self):
        mensagem = update("/start {}".format(CodigoVinculoTelegram.emitir(self.ana)))
        del mensagem["message"]["from"]["username"], mensagem["message"]["from"]["last_name"]

        recebimento.receber(mensagem)

        vinculo = VinculoTelegram.objects.get()
        self.assertEqual(vinculo.username, "")
        self.assertEqual(vinculo.nome, "Ana")


class StartSemCodigoTestCase(BotTestCase):

    def test_quem_nao_esta_conectado_recebe_a_explicacao(self):
        resposta = self.enviar("/start")

        self.assertIn(comandos.BOAS_VINDAS, resposta["text"])
        self.assertIn(comandos.COMO_CONECTAR, resposta["text"])

    def test_quem_esta_conectado_recebe_a_ajuda(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        resposta = self.enviar("/start")

        self.assertIn(comandos.BOAS_VINDAS, resposta["text"])
        self.assertIn(comandos.AJUDA, resposta["text"])
        self.assertNotIn(comandos.COMO_CONECTAR, resposta["text"])


class DesconectarTestCase(BotTestCase):

    def test_apaga_o_vinculo_e_confirma(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        resposta = self.enviar("/desconectar")

        self.assertEqual(resposta["text"], comandos.DESCONECTADO)
        self.assertFalse(VinculoTelegram.objects.exists())

    def test_sem_vinculo_avisa_que_nao_esta_conectado(self):
        self.assertEqual(self.enviar("/desconectar")["text"], comandos.NAO_CONECTADO)

    def test_so_apaga_o_vinculo_de_quem_mandou(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.enviar("/desconectar", telegram_id=TELEGRAM_BIA)

        self.assertTrue(VinculoTelegram.objects.filter(usuario=self.ana).exists())


class UsuarioDesativadoTestCase(BotTestCase):

    def setUp(self):
        super().setUp()
        self.vincular(self.ana, TELEGRAM_ANA)
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

    def test_vinculo_nao_vale(self):
        self.assertIsNone(services.vinculo_valido(TELEGRAM_ANA))

    def test_bot_trata_como_nao_conectado(self):
        self.assertIn(comandos.COMO_CONECTAR, self.enviar("/start")["text"])
        self.assertEqual(self.enviar("/desconectar")["text"], comandos.NAO_CONECTADO)

    def test_log_nao_atribui_a_mensagem_ao_usuario(self):
        self.enviar("/start")

        self.assertIsNone(MensagemTelegram.objects.get(direcao=MensagemTelegram.Direcao.ENTRADA).usuario)

    def test_reativar_devolve_o_acesso(self):
        User.objects.filter(pk=self.ana.pk).update(is_active=True)

        self.assertIn(comandos.AJUDA, self.enviar("/start")["text"])


class LogDeEntradaTestCase(BotTestCase):

    def entrada(self):
        return MensagemTelegram.objects.get(direcao=MensagemTelegram.Direcao.ENTRADA)

    def test_mascarar_start(self):
        casos = {
            "/start abc": "/start ***",
            "/start   abc def": "/start ***",
            "/start\nabc": "/start ***",
            "/START abc": "/START ***",
            "/start@sigep_bot abc": "/start@sigep_bot ***",
            "/start": "/start",
            "/desconectar": "/desconectar",
            "olá /start abc": "olá /start abc",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(recebimento.mascarar_start(texto), esperado)

    def test_codigo_nao_fica_no_log_de_quem_nao_esta_conectado(self):
        token = CodigoVinculoTelegram.emitir(self.ana)

        self.enviar("/start {}".format(token))

        self.assertEqual(self.entrada().texto, "/start ***")
        self.assertIsNone(self.entrada().conteudo)
        self.assertNotIn(token, str(list(MensagemTelegram.objects.values())))

    def test_codigo_nao_fica_no_json_de_quem_ja_esta_conectado(self):
        self.vincular(self.ana, TELEGRAM_ANA)
        token = CodigoVinculoTelegram.emitir(self.bia)

        self.enviar("/start {}".format(token))

        self.assertEqual(self.entrada().conteudo["message"]["text"], "/start ***")
        self.assertNotIn(token, str(list(MensagemTelegram.objects.values())))

    def test_codigo_invalido_tambem_e_mascarado(self):
        self.enviar("/start nao-existe")

        self.assertEqual(self.entrada().texto, "/start ***")

    def test_registra_quem_mandou_e_o_resultado(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.enviar("/start")

        entrada = self.entrada()
        self.assertEqual(entrada.usuario, self.ana)
        self.assertEqual(entrada.telegram_id, TELEGRAM_ANA)
        self.assertEqual(entrada.tipo, "comando")
        self.assertEqual(entrada.situacao, MensagemTelegram.Situacao.PROCESSADA)

    def test_atualiza_a_conversa_e_o_ultimo_uso_de_quem_esta_conectado(self):
        vinculo = self.vincular(self.ana, TELEGRAM_ANA)
        VinculoTelegram.objects.filter(pk=vinculo.pk).update(chat_id=1)

        self.enviar("/start")

        vinculo.refresh_from_db()
        self.assertEqual(vinculo.chat_id, TELEGRAM_ANA)
        self.assertIsNotNone(vinculo.ultimo_uso)

    def test_grupo_nao_gasta_o_codigo(self):
        token = CodigoVinculoTelegram.emitir(self.ana)

        self.assertIsNone(self.enviar("/start {}".format(token), tipo_chat="group"))

        self.assertIsNotNone(CodigoVinculoTelegram.buscar_valido(token))


@override_settings(TELEGRAM_BOT_USERNAME="sigep_bot")
class TelaTelegramTestCase(BotTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)
        self.url = reverse("telegram:conexao")

    def conectar(self):
        return self.client.post(reverse("telegram:conectar"), follow=True)

    def test_exige_login(self):
        self.client.logout()

        for url in (self.url, reverse("telegram:conectar"), reverse("telegram:desconectar")):
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.post(url), "{}?next={}".format(reverse("login"), url), fetch_redirect_response=False,
                )

    def test_menu_do_usuario_tem_a_tela(self):
        self.assertContains(self.client.get(self.url), 'class="dropdown-item" href="{}"'.format(self.url))

    def test_desconectado_mostra_o_botao_de_conectar(self):
        resposta = self.client.get(self.url)

        self.assertContains(resposta, reverse("telegram:conectar"))
        self.assertNotContains(resposta, "t.me/")

    def test_conectar_guarda_o_token_na_sessao_e_mostra_o_link(self):
        resposta = self.conectar()

        token = self.client.session[CHAVE_SESSAO_CODIGO]
        self.assertEqual(CodigoVinculoTelegram.buscar_valido(token).usuario, self.ana)
        self.assertContains(resposta, "https://t.me/sigep_bot?start={}".format(token))
        self.assertContains(resposta, "15 minutos")
        self.assertContains(resposta, "uma vez")

    def test_get_nao_gera_codigo(self):
        self.client.get(self.url)

        self.assertFalse(CodigoVinculoTelegram.objects.exists())

    def test_codigo_vencido_volta_para_o_botao_de_conectar(self):
        self.conectar()
        CodigoVinculoTelegram.objects.update(expira_em=timezone.now() - timedelta(seconds=1))

        resposta = self.client.get(self.url)

        self.assertNotContains(resposta, "t.me/")
        self.assertContains(resposta, reverse("telegram:conectar"))
        self.assertNotIn(CHAVE_SESSAO_CODIGO, self.client.session)

    def test_conectado_mostra_os_dados_do_telegram(self):
        vinculo = self.vincular(self.ana, TELEGRAM_ANA)
        VinculoTelegram.objects.filter(pk=vinculo.pk).update(username="ana_tg", nome="Ana Souza")

        resposta = self.client.get(self.url)

        self.assertContains(resposta, "Ana Souza")
        self.assertContains(resposta, "@ana_tg")
        self.assertContains(resposta, timezone.localtime(vinculo.vinculado_em).strftime("%d/%m/%Y %H:%M"))
        self.assertContains(resposta, reverse("telegram:desconectar"))
        self.assertContains(resposta, "form-confirmar")

    def test_tela_passa_a_conectado_depois_do_start(self):
        self.conectar()
        self.enviar("/start {}".format(self.client.session[CHAVE_SESSAO_CODIGO]))

        resposta = self.client.get(self.url)

        self.assertContains(resposta, "Ana Souza")
        self.assertNotContains(resposta, "t.me/")

    def test_conectado_nao_gera_codigo_novo(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.conectar()

        self.assertFalse(CodigoVinculoTelegram.objects.exists())

    def test_desconectar_apaga_so_o_proprio_vinculo(self):
        self.vincular(self.ana, TELEGRAM_ANA)
        self.vincular(self.bia, TELEGRAM_BIA)

        resposta = self.client.post(reverse("telegram:desconectar"), follow=True)

        self.assertRedirects(resposta, self.url)
        self.assertEqual(VinculoTelegram.objects.get().usuario, self.bia)

    def test_conectar_e_desconectar_nao_aceitam_get(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.assertEqual(self.client.get(reverse("telegram:conectar")).status_code, 405)
        self.assertEqual(self.client.get(reverse("telegram:desconectar")).status_code, 405)
        self.assertTrue(VinculoTelegram.objects.exists())


class ComandoWebhookTestCase(TestCase):

    def setUp(self):
        self.cliente = obter_cliente()
        self.cliente.limpar()

    @override_settings(TELEGRAM_BOT_WEBHOOK_URL="https://sigep.exemplo.com/telegram/webhook/", TELEGRAM_WEBHOOK_SECRET=SEGREDO)
    def test_registra_a_url_e_o_segredo(self):
        call_command("telegram_webhook", stdout=StringIO())

        chamada = self.cliente.mensagens[0]
        self.assertEqual(chamada["metodo"], "setWebhook")
        self.assertEqual(chamada["url"], "https://sigep.exemplo.com/telegram/webhook/")
        self.assertEqual(chamada["secret_token"], SEGREDO)
        self.assertEqual(chamada["allowed_updates"], ["message", "callback_query"])

    @override_settings(TELEGRAM_BOT_WEBHOOK_URL="", TELEGRAM_WEBHOOK_SECRET=SEGREDO)
    def test_sem_a_url_nao_chama_o_telegram(self):
        with self.assertRaises(CommandError):
            call_command("telegram_webhook", stdout=StringIO())

        self.assertEqual(self.cliente.mensagens, [])

    @override_settings(TELEGRAM_BOT_WEBHOOK_URL="https://sigep.exemplo.com/telegram/webhook/", TELEGRAM_WEBHOOK_SECRET=SEGREDO)
    def test_recusa_do_telegram_vira_erro(self):
        self.cliente.programar("setWebhook", None)

        with self.assertRaises(CommandError):
            call_command("telegram_webhook", stdout=StringIO())
