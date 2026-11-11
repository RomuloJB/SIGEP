import json
import logging
from unittest import mock
from urllib.parse import quote

import httpx
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from telegram.cliente import ClienteFalso, ClienteTelegram, botao, botao_link, obter_cliente
from telegram.models import MensagemTelegram

TOKEN = "123456:TOKEN-secreto_do_bot"
SEGREDO = "segredo-do-webhook"


def ok(resultado=True):
    return httpx.Response(200, json={"ok": True, "result": resultado})


def erro_api(status, descricao, **extras):
    return httpx.Response(status, json={"ok": False, "error_code": status, "description": descricao, **extras})


def muitos_pedidos(retry_after):
    return erro_api(429, "Too Many Requests", parameters={"retry_after": retry_after})


class Pedacos(httpx.SyncByteStream):
    """Corpo de resposta que conta quantos pedaços foram lidos."""

    def __init__(self, pedacos):
        self.pedacos = pedacos
        self.lidos = 0

    def __iter__(self):
        for pedaco in self.pedacos:
            self.lidos += 1
            yield pedaco


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_WEBHOOK_SECRET=SEGREDO, TELEGRAM_RETRY_MAX_S=5)
class ClienteTelegramTestCase(TestCase):

    def setUp(self):
        self.pedidos = []
        self.respostas = []  # o que cada requisição devolve, na ordem (resposta ou exceção)
        self.cliente = ClienteTelegram(transporte=httpx.MockTransport(self.responder))
        sono = mock.patch("telegram.cliente.time.sleep")
        self.sono = sono.start()
        self.addCleanup(sono.stop)

    def responder(self, pedido):
        self.pedidos.append(pedido)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def corpo(self, indice=0):
        return json.loads(self.pedidos[indice].content)

    def assertSemSegredos(self, *textos):
        """Nem o token nem o segredo em nenhum campo do log, nem nos textos informados."""
        tudo = str(list(MensagemTelegram.objects.values())) + " ".join(str(texto) for texto in textos)
        self.assertNotIn(TOKEN, tudo)
        self.assertNotIn(quote(TOKEN, safe=""), tudo)
        self.assertNotIn(SEGREDO, tudo)

    # ─── Sucesso e log ────────────────────────────────────────────────────────

    def test_sucesso_devolve_result_e_grava_saida(self):
        self.respostas = [ok({"message_id": 7, "text": "oi"})]

        resultado = self.cliente.chamar("sendMessage", chat_id=10_000_000_000, text="oi", vazio=None)

        self.assertEqual(resultado, {"message_id": 7, "text": "oi"})
        self.assertEqual(str(self.pedidos[0].url), "https://api.telegram.org/bot{}/sendMessage".format(TOKEN))
        self.assertEqual(self.corpo(), {"chat_id": 10_000_000_000, "text": "oi"})  # None não é enviado

        registro = MensagemTelegram.objects.get()
        self.assertEqual(registro.direcao, MensagemTelegram.Direcao.SAIDA)
        self.assertEqual(registro.situacao, MensagemTelegram.Situacao.ENVIADA)
        self.assertEqual(registro.metodo_api, "sendMessage")
        self.assertEqual(registro.chat_id, 10_000_000_000)
        self.assertEqual(registro.mensagem_id, 7)
        self.assertEqual(registro.texto, "oi")
        self.assertEqual(registro.status_http, 200)
        self.assertEqual(registro.erro, "")
        self.assertIsNotNone(registro.duracao_ms)
        self.assertIsNone(registro.update_id)

    def test_contexto_preenche_o_log_e_json_so_de_quem_esta_conectado(self):
        usuario = User.objects.create_user("ana", password="x")
        self.respostas = [ok({"message_id": 1}), ok({"message_id": 2})]

        self.cliente.enviar(5, "conectada", contexto={"usuario": usuario, "telegram_id": 99, "tipo": "comando"})
        self.cliente.enviar(6, "desconhecido")

        conectada = MensagemTelegram.objects.get(chat_id=5)
        self.assertEqual(conectada.usuario, usuario)
        self.assertEqual(conectada.telegram_id, 99)
        self.assertEqual(conectada.tipo, "comando")
        self.assertEqual(conectada.conteudo["text"], "conectada")
        self.assertIsNone(MensagemTelegram.objects.get(chat_id=6).conteudo)

    # ─── Falhas ───────────────────────────────────────────────────────────────

    def test_falha_de_rede_devolve_none_e_grava_falhou(self):
        self.respostas = [httpx.ConnectTimeout("demorou")]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        registro = MensagemTelegram.objects.get()
        self.assertEqual(registro.situacao, MensagemTelegram.Situacao.FALHOU)
        self.assertIn("ConnectTimeout", registro.erro)
        self.assertIsNone(registro.status_http)

    def test_erro_da_api_devolve_none_com_a_descricao(self):
        self.respostas = [erro_api(400, "Bad Request: chat not found")]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        registro = MensagemTelegram.objects.get()
        self.assertEqual(registro.status_http, 400)
        self.assertEqual(registro.erro, "Bad Request: chat not found")

    def test_resposta_que_nao_e_json_devolve_none(self):
        self.respostas = [httpx.Response(502, text="<html>Bad Gateway</html>")]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.assertEqual(MensagemTelegram.objects.get().erro, "HTTP 502")

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_sem_token_devolve_none_sem_usar_a_rede(self):
        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.assertEqual(self.pedidos, [])
        self.assertIn("TELEGRAM_BOT_TOKEN", MensagemTelegram.objects.get().erro)

    def test_falha_ao_gravar_o_log_nao_derruba_a_chamada(self):
        self.respostas = [ok({"message_id": 7})]

        with mock.patch("telegram.cliente.MensagemTelegram.objects.create", side_effect=DatabaseError("sem banco")):
            with self.assertLogs("telegram.cliente", level="ERROR"):
                resultado = self.cliente.enviar(1, "oi")

        self.assertEqual(resultado, {"message_id": 7})

    def test_403_e_429_ficam_fora_do_log_de_erros(self):
        self.respostas = [erro_api(403, "Forbidden: bot was blocked by the user"), muitos_pedidos(30)]

        with self.assertNoLogs("telegram.cliente", level="WARNING"):
            self.assertIsNone(self.cliente.enviar(1, "oi"))
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        # Fora do log de erros do sistema, mas continuam no log de mensagens
        self.assertEqual(MensagemTelegram.objects.filter(situacao=MensagemTelegram.Situacao.FALHOU).count(), 2)

    # ─── Token e segredo ──────────────────────────────────────────────────────

    def test_token_nao_aparece_quando_a_excecao_traz_a_url(self):
        url = "https://api.telegram.org/bot{}/sendMessage".format(TOKEN)
        self.respostas = [httpx.ConnectError("falha em " + url), httpx.ConnectError("falha em " + quote(url, safe=""))]

        with self.assertLogs("telegram.cliente", level="ERROR") as logs:
            self.assertIsNone(self.cliente.enviar(1, "oi"))
            self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.assertSemSegredos(logs.output)
        self.assertEqual(MensagemTelegram.objects.filter(erro__contains="***").count(), 2)

    def test_token_nao_aparece_quando_a_api_devolve_ele_no_erro(self):
        self.respostas = [erro_api(401, "Unauthorized: bot{}".format(TOKEN))]

        with self.assertLogs("telegram.cliente", level="ERROR") as logs:
            self.cliente.enviar(1, "oi")

        self.assertSemSegredos(logs.output)

    def test_token_nao_aparece_no_texto_nem_no_json(self):
        usuario = User.objects.create_user("ana", password="x")
        self.respostas = [ok({"message_id": 1})]

        self.cliente.enviar(1, "token: {}".format(TOKEN), contexto={"usuario": usuario})

        self.assertSemSegredos()

    def test_segredo_do_webhook_nao_vai_para_o_log(self):
        usuario = User.objects.create_user("ana", password="x")
        self.respostas = [ok(True)]

        self.cliente.chamar("setWebhook", contexto={"usuario": usuario}, url="https://x", secret_token=SEGREDO)

        self.assertEqual(self.corpo()["secret_token"], SEGREDO)  # para o Telegram vai o valor real
        self.assertEqual(MensagemTelegram.objects.get().conteudo["secret_token"], "***")
        self.assertSemSegredos()

    def test_httpx_nao_escreve_a_url_com_o_token(self):
        self.assertFalse(logging.getLogger("httpx").isEnabledFor(logging.INFO))

    # ─── 429 e "message is not modified" ──────────────────────────────────────

    def test_429_com_espera_curta_tenta_de_novo_uma_vez(self):
        self.respostas = [muitos_pedidos(3), ok({"message_id": 7})]

        self.assertEqual(self.cliente.enviar(1, "oi"), {"message_id": 7})

        self.sono.assert_called_once_with(3)
        self.assertEqual(len(self.pedidos), 2)
        self.assertEqual(MensagemTelegram.objects.get().situacao, MensagemTelegram.Situacao.ENVIADA)

    def test_429_repetido_nao_tenta_uma_terceira_vez(self):
        self.respostas = [muitos_pedidos(1), muitos_pedidos(1)]

        self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.assertEqual(len(self.pedidos), 2)
        self.sono.assert_called_once_with(1)

    def test_429_com_espera_longa_nao_espera(self):
        self.respostas = [muitos_pedidos(6)]

        self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.assertEqual(len(self.pedidos), 1)
        self.sono.assert_not_called()

    def test_429_sem_retry_after_nao_espera(self):
        self.respostas = [erro_api(429, "Too Many Requests")]

        self.assertIsNone(self.cliente.enviar(1, "oi"))

        self.sono.assert_not_called()

    def test_mensagem_nao_modificada_conta_como_sucesso(self):
        self.respostas = [erro_api(400, "Bad Request: message is not modified: specified new message content")]

        with self.assertNoLogs("telegram.cliente", level="WARNING"):
            self.assertIs(self.cliente.editar(1, 7, "igual"), True)

        registro = MensagemTelegram.objects.get()
        self.assertEqual(registro.situacao, MensagemTelegram.Situacao.ENVIADA)
        self.assertEqual(registro.erro, "")
        self.assertEqual(registro.mensagem_id, 7)

    # ─── Atalhos ──────────────────────────────────────────────────────────────

    def test_enviar_usa_html_e_monta_o_teclado(self):
        self.respostas = [ok({"message_id": 1})]

        self.cliente.enviar(1, "<b>oi</b>", teclado=[[botao("Confirmar", "ok:45")]])

        self.assertEqual(self.pedidos[0].url.path.rsplit("/", 1)[-1], "sendMessage")
        self.assertEqual(self.corpo(), {
            "chat_id": 1,
            "text": "<b>oi</b>",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "Confirmar", "callback_data": "ok:45"}]]},
        })

    def test_editar_sem_teclado_nao_envia_reply_markup(self):
        self.respostas = [ok({"message_id": 7})]

        self.cliente.editar(1, 7, "novo")

        self.assertEqual(self.pedidos[0].url.path.rsplit("/", 1)[-1], "editMessageText")
        self.assertEqual(self.corpo(), {"chat_id": 1, "message_id": 7, "text": "novo", "parse_mode": "HTML"})

    def test_apagar(self):
        self.respostas = [ok(True)]

        self.assertIs(self.cliente.apagar(1, 7), True)

        self.assertEqual(self.pedidos[0].url.path.rsplit("/", 1)[-1], "deleteMessage")
        self.assertEqual(self.corpo(), {"chat_id": 1, "message_id": 7})
        self.assertEqual(MensagemTelegram.objects.get().mensagem_id, 7)

    def test_responder_botao_corta_o_texto_em_200_caracteres(self):
        self.respostas = [ok(True), ok(True)]

        self.cliente.responder_botao("abc", "x" * 300, alerta=True)
        self.cliente.responder_botao("def")

        self.assertEqual(self.pedidos[0].url.path.rsplit("/", 1)[-1], "answerCallbackQuery")
        self.assertEqual(self.corpo(0), {"callback_query_id": "abc", "text": "x" * 200, "show_alert": True})
        self.assertEqual(self.corpo(1), {"callback_query_id": "def", "show_alert": False})

    # ─── Download ─────────────────────────────────────────────────────────────

    def test_baixar_arquivo_devolve_os_bytes(self):
        self.respostas = [ok({"file_path": "photos/a.jpg"}), httpx.Response(200, stream=Pedacos([b"abc", b"def"]))]

        self.assertEqual(self.cliente.baixar_arquivo("id1", 6), b"abcdef")

        self.assertEqual(str(self.pedidos[1].url), "https://api.telegram.org/file/bot{}/photos/a.jpg".format(TOKEN))
        self.assertEqual(
            list(MensagemTelegram.objects.order_by("pk").values_list("metodo_api", "situacao")),
            [("getFile", "enviada"), ("downloadFile", "enviada")],
        )
        self.assertSemSegredos()

    def test_baixar_arquivo_para_no_limite_sem_ler_o_resto(self):
        corpo = Pedacos([b"aaaa", b"bbbb", b"cccc", b"dddd"])
        self.respostas = [ok({"file_path": "a.pdf"}), httpx.Response(200, stream=corpo)]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.baixar_arquivo("id1", 5))

        self.assertEqual(corpo.lidos, 2)
        self.assertIn("limite", MensagemTelegram.objects.get(metodo_api="downloadFile").erro)

    def test_baixar_arquivo_com_falha_no_get_file_nao_tenta_o_download(self):
        self.respostas = [erro_api(400, "Bad Request: wrong file_id")]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.baixar_arquivo("id1", 5))

        self.assertEqual(len(self.pedidos), 1)

    def test_baixar_arquivo_com_falha_no_download_devolve_none_sem_o_token(self):
        url = "https://api.telegram.org/file/bot{}/a.pdf".format(TOKEN)
        self.respostas = [ok({"file_path": "a.pdf"}), httpx.ReadTimeout("demorou em " + url)]

        with self.assertLogs("telegram.cliente", level="ERROR") as logs:
            self.assertIsNone(self.cliente.baixar_arquivo("id1", 5))

        self.assertSemSegredos(logs.output)

    def test_baixar_arquivo_com_status_de_erro_devolve_none(self):
        self.respostas = [ok({"file_path": "a.pdf"}), httpx.Response(404, text="não achei")]

        with self.assertLogs("telegram.cliente", level="ERROR"):
            self.assertIsNone(self.cliente.baixar_arquivo("id1", 50))

        self.assertEqual(MensagemTelegram.objects.get(metodo_api="downloadFile").status_http, 404)


class BotaoTestCase(SimpleTestCase):

    def test_dados_no_limite_de_64_bytes(self):
        self.assertEqual(botao("Ok", "x" * 64), {"text": "Ok", "callback_data": "x" * 64})

    def test_dados_longos_falham(self):
        with self.assertRaises(ValueError):
            botao("Ok", "x" * 65)

    def test_limite_e_em_bytes_nao_em_caracteres(self):
        with self.assertRaises(ValueError):
            botao("Ok", "á" * 33)  # 33 caracteres, 66 bytes

    def test_rotulo_longo_e_cortado(self):
        rotulo = botao("x" * 100, "ok:1")["text"]

        self.assertEqual(len(rotulo), 40)
        self.assertTrue(rotulo.endswith("…"))

    def test_rotulo_no_limite_fica_inteiro(self):
        self.assertEqual(botao("x" * 40, "ok:1")["text"], "x" * 40)

    def test_botao_de_link(self):
        self.assertEqual(botao_link("Abrir", "https://exemplo.com/"), {"text": "Abrir", "url": "https://exemplo.com/"})

    def test_botao_de_link_corta_o_rotulo(self):
        self.assertEqual(len(botao_link("x" * 100, "https://exemplo.com/")["text"]), 40)


class ClienteFalsoTestCase(SimpleTestCase):

    def setUp(self):
        self.cliente = ClienteFalso()

    def test_obter_cliente_nos_testes_devolve_sempre_o_mesmo_falso(self):
        self.assertIsInstance(obter_cliente(), ClienteFalso)
        self.assertIs(obter_cliente(), obter_cliente())

    def test_guarda_as_mensagens_em_ordem(self):
        primeira = self.cliente.enviar(1, "oi")
        segunda = self.cliente.enviar(1, "tudo bem?")
        self.cliente.responder_botao("abc", "feito")

        self.assertEqual((primeira["message_id"], segunda["message_id"]), (1, 2))
        self.assertEqual([m["metodo"] for m in self.cliente.mensagens], ["sendMessage", "sendMessage", "answerCallbackQuery"])
        self.assertEqual(self.cliente.mensagens[0]["text"], "oi")
        self.assertEqual(self.cliente.mensagens[0]["parse_mode"], "HTML")

    def test_programar_simula_uma_falha_so_na_proxima_chamada(self):
        self.cliente.programar("editMessageText", None)

        self.assertIsNone(self.cliente.editar(1, 7, "novo"))
        self.assertIs(self.cliente.editar(1, 7, "novo"), True)

    def test_baixar_arquivo_respeita_o_limite(self):
        self.cliente.arquivos["id1"] = b"abcdef"

        self.assertEqual(self.cliente.baixar_arquivo("id1", 6), b"abcdef")
        self.assertIsNone(self.cliente.baixar_arquivo("id1", 5))
        self.assertIsNone(self.cliente.baixar_arquivo("outro", 5))

    def test_limpar_esquece_tudo(self):
        self.cliente.enviar(1, "oi")
        self.cliente.programar("sendMessage", None)
        self.cliente.arquivos["id1"] = b"abc"

        self.cliente.limpar()

        self.assertEqual(self.cliente.mensagens, [])
        self.assertEqual(self.cliente.arquivos, {})
        self.assertEqual(self.cliente.enviar(1, "oi")["message_id"], 1)
