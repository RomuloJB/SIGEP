import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from telegram import manutencao
from telegram.cliente import ClienteFalso, obter_cliente
from telegram.comandos import COMANDOS_DO_MENU, DESCRICAO_CURTA_DO_BOT, DESCRICAO_DO_BOT, NOME_DO_BOT
from telegram.models import CodigoVinculoTelegram, ConfiguracaoTelegram, LimiteTelegram, MensagemTelegram

SEGREDO = "segredo-do-webhook"
TAREFAS = "segredo-das-tarefas"
URL = "https://sigep.exemplo.com/telegram/webhook/"


def rodar(*args):
    """Roda o comando e devolve (saída, erros). Levanta CommandError como o terminal mostraria."""
    saida, erros = StringIO(), StringIO()
    call_command("telegram_definir_webhook", *args, stdout=saida, stderr=erros)
    return saida.getvalue(), erros.getvalue()


@override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_BOT_WEBHOOK_URL=URL, TELEGRAM_WEBHOOK_SECRET=SEGREDO)
class DefinirWebhookTestCase(TestCase):

    def setUp(self):
        self.cliente = obter_cliente()
        self.cliente.limpar()

    def chamada(self, metodo):
        return next(m for m in self.cliente.mensagens if m["metodo"] == metodo)

    def metodos(self):
        return [m["metodo"] for m in self.cliente.mensagens]

    def test_configura_textos_menu_e_webhook(self):
        saida, erros = rodar()

        self.assertEqual(self.metodos(), [
            "getMyName", "setMyName", "getMyDescription", "setMyDescription",
            "getMyShortDescription", "setMyShortDescription", "setMyCommands", "setChatMenuButton", "setWebhook",
        ])
        self.assertEqual(self.chamada("setMyName")["name"], NOME_DO_BOT)
        self.assertEqual(self.chamada("setMyDescription")["description"], DESCRICAO_DO_BOT)
        self.assertEqual(self.chamada("setMyShortDescription")["short_description"], DESCRICAO_CURTA_DO_BOT)
        self.assertEqual(
            self.chamada("setMyCommands")["commands"],
            [{"command": nome, "description": descricao} for nome, descricao in COMANDOS_DO_MENU],
        )
        self.assertEqual(self.chamada("setChatMenuButton")["menu_button"], {"type": "commands"})
        self.assertIn("Bot configurado", saida)
        self.assertEqual(erros, "")

    def test_webhook_com_segredo_e_sem_descartar_pendentes(self):
        rodar()

        webhook = self.chamada("setWebhook")
        self.assertEqual(webhook["url"], URL)
        self.assertEqual(webhook["secret_token"], SEGREDO)
        self.assertEqual(webhook["allowed_updates"], ["message", "callback_query"])
        self.assertEqual(webhook["max_connections"], settings.TELEGRAM_MAX_CONEXOES)
        self.assertNotIn("drop_pending_updates", webhook)

    def test_texto_que_ja_esta_certo_nao_e_enviado_de_novo(self):
        self.cliente.programar("getMyName", {"name": NOME_DO_BOT})
        self.cliente.programar("getMyDescription", {"description": DESCRICAO_DO_BOT})
        self.cliente.programar("getMyShortDescription", {"short_description": "texto antigo"})

        saida, _ = rodar()

        self.assertNotIn("setMyName", self.metodos())
        self.assertNotIn("setMyDescription", self.metodos())
        self.assertIn("setMyShortDescription", self.metodos())
        self.assertIn("Nome: já estava atualizado", saida)

    def test_url_so_com_a_raiz_ganha_o_caminho_do_webhook(self):
        for url in ("https://sigep.exemplo.com", "https://sigep.exemplo.com/", "https://sigep.exemplo.com/telegram/webhook"):
            with self.subTest(url=url), override_settings(TELEGRAM_BOT_WEBHOOK_URL=url):
                self.cliente.limpar()
                rodar()
                self.assertEqual(self.chamada("setWebhook")["url"], URL)

    def test_url_com_outro_caminho_e_recusada(self):
        with override_settings(TELEGRAM_BOT_WEBHOOK_URL="https://sigep.exemplo.com/outro/"):
            with self.assertRaisesMessage(CommandError, "/telegram/webhook/"):
                rodar()
        self.assertEqual(self.cliente.mensagens, [])

    def test_url_sem_https_e_recusada(self):
        for url in ("http://sigep.exemplo.com/telegram/webhook/", "sigep.exemplo.com"):
            with self.subTest(url=url), override_settings(TELEGRAM_BOT_WEBHOOK_URL=url):
                with self.assertRaisesMessage(CommandError, "https://"):
                    rodar()
        self.assertEqual(self.cliente.mensagens, [])

    def test_variaveis_faltando_sao_listadas_sem_chamar_o_telegram(self):
        with override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_WEBHOOK_SECRET=""):
            with self.assertRaises(CommandError) as erro:
                rodar()
        self.assertIn("TELEGRAM_BOT_TOKEN", str(erro.exception))
        self.assertIn("TELEGRAM_WEBHOOK_SECRET", str(erro.exception))
        self.assertNotIn("TELEGRAM_BOT_WEBHOOK_URL", str(erro.exception))
        self.assertEqual(self.cliente.mensagens, [])

    def test_falha_mostra_o_motivo_do_log_e_os_outros_passos_continuam(self):
        chamar_original = ClienteFalso.chamar

        def chamar(cliente, metodo, contexto=None, **params):
            if metodo != "setMyName":
                return chamar_original(cliente, metodo, contexto, **params)
            # O cliente real grava a falha no log; o comando lê o motivo de lá
            MensagemTelegram.objects.create(
                direcao=MensagemTelegram.Direcao.SAIDA, metodo_api=metodo, situacao=MensagemTelegram.Situacao.FALHOU,
                erro="Too Many Requests: retry after 600",
            )
            return None

        with mock.patch.object(ClienteFalso, "chamar", chamar):
            with self.assertRaisesMessage(CommandError, "1 passo(s) falharam"):
                rodar()

        self.assertIn("setWebhook", self.metodos())

    def test_falha_do_webhook_sem_log_tem_motivo_generico(self):
        self.cliente.programar("setWebhook", None)
        erros = StringIO()

        with self.assertRaises(CommandError):
            call_command("telegram_definir_webhook", stdout=StringIO(), stderr=erros)

        self.assertIn("[erro] Webhook", erros.getvalue())
        self.assertIn("Log do Telegram", erros.getvalue())

    def test_textos_respeitam_os_limites_do_telegram(self):
        self.assertLessEqual(len(NOME_DO_BOT), 64)
        self.assertLessEqual(len(DESCRICAO_DO_BOT), 512)
        self.assertLessEqual(len(DESCRICAO_CURTA_DO_BOT), 120)
        self.assertNotIn("<", DESCRICAO_DO_BOT + DESCRICAO_CURTA_DO_BOT)  # descrições não aceitam HTML
        for nome, descricao in COMANDOS_DO_MENU:
            with self.subTest(comando=nome):
                self.assertRegex(nome, r"^[a-z0-9_]{1,32}$")
                self.assertTrue(1 <= len(descricao) <= 256)

    # ─── --info e --remover ───────────────────────────────────────────────────

    def test_info_mostra_url_pendentes_e_ultimo_erro(self):
        momento = datetime(2026, 11, 7, 15, 30, tzinfo=dt_timezone.utc)
        self.cliente.programar("getWebhookInfo", {
            "url": URL, "pending_update_count": 3,
            "last_error_date": int(momento.timestamp()), "last_error_message": "Connection timed out",
        })

        saida, erros = rodar("--info")

        self.assertIn("URL registrada: " + URL, saida)
        self.assertIn("Mensagens pendentes: 3", erros)
        self.assertIn("Último erro: 07/11/2026 12:30: Connection timed out", erros)  # horário de Brasília
        self.assertEqual(self.metodos(), ["getWebhookInfo"])

    def test_info_sem_erros(self):
        self.cliente.programar("getWebhookInfo", {"url": URL, "pending_update_count": 0})

        saida, erros = rodar("--info")

        self.assertIn("Mensagens pendentes: 0", saida)
        self.assertIn("Nenhum erro recente", saida)
        self.assertEqual(erros, "")

    def test_info_avisa_quando_a_url_registrada_e_outra(self):
        self.cliente.programar("getWebhookInfo", {"url": "https://antigo.ngrok-free.app/telegram/webhook/"})

        _, erros = rodar("--info")

        self.assertIn("A URL do .env é outra ({})".format(URL), erros)

    def test_info_sem_webhook_registrado(self):
        self.cliente.programar("getWebhookInfo", {"url": ""})

        _, erros = rodar("--info")

        self.assertIn("Nenhum webhook registrado", erros)

    @override_settings(TELEGRAM_BOT_WEBHOOK_URL="", TELEGRAM_WEBHOOK_SECRET="")
    def test_info_e_remover_so_precisam_do_token(self):
        self.cliente.programar("getWebhookInfo", {"url": ""})

        rodar("--info")
        rodar("--remover")

        self.assertEqual(self.metodos(), ["getWebhookInfo", "deleteWebhook"])

    def test_remover_nao_descarta_pendentes(self):
        saida, _ = rodar("--remover")

        self.assertEqual(self.cliente.mensagens, [{"metodo": "deleteWebhook"}])
        self.assertIn("Webhook removido", saida)

    def test_falha_no_info_e_no_remover_vira_erro(self):
        self.cliente.programar("getWebhookInfo", None)
        self.cliente.programar("deleteWebhook", None)

        with self.assertRaises(CommandError):
            rodar("--info")
        with self.assertRaises(CommandError):
            rodar("--remover")

    def test_info_e_remover_juntos_nao_valem(self):
        with self.assertRaises(CommandError):
            rodar("--info", "--remover")
        self.assertEqual(self.cliente.mensagens, [])


class LimpezaTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        self.addCleanup(cache.delete, ConfiguracaoTelegram.CHAVE_CACHE)
        self.agora = timezone.now()

    def mensagem(self, dias, conteudo=None):
        mensagem = MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.ENTRADA, situacao=MensagemTelegram.Situacao.PROCESSADA,
            texto="oi", conteudo=conteudo,
        )
        MensagemTelegram.objects.filter(pk=mensagem.pk).update(criado_em=self.agora - timedelta(days=dias))
        return mensagem

    def contador(self, telegram_id, dias_parado, bloqueado_ate=None):
        limite = LimiteTelegram.objects.create(telegram_id=telegram_id, bloqueado_ate=bloqueado_ate)
        LimiteTelegram.objects.filter(pk=limite.pk).update(ultima_vez=self.agora - timedelta(days=dias_parado))
        return limite

    def test_json_sai_depois_do_prazo_e_a_mensagem_fica(self):
        antiga = self.mensagem(31, conteudo={"update_id": 1})
        recente = self.mensagem(29, conteudo={"update_id": 2})

        resultado = manutencao.limpar()

        antiga.refresh_from_db()
        recente.refresh_from_db()
        self.assertIsNone(antiga.conteudo)
        self.assertEqual(antiga.texto, "oi")
        self.assertEqual(recente.conteudo, {"update_id": 2})
        self.assertEqual(resultado["conteudos_apagados"], 1)

    def test_mensagens_saem_depois_do_prazo(self):
        self.mensagem(61, conteudo={"update_id": 1})
        recente = self.mensagem(59)

        resultado = manutencao.limpar()

        self.assertEqual(list(MensagemTelegram.objects.all()), [recente])
        self.assertEqual(resultado["mensagens_apagadas"], 1)
        self.assertEqual(resultado["conteudos_apagados"], 0)  # a apagada não conta duas vezes

    def test_usa_os_prazos_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.reter_conteudo_dias, config.reter_mensagens_dias = 2, 5
        config.save()
        com_json = self.mensagem(3, conteudo={"update_id": 1})
        self.mensagem(6)

        manutencao.limpar()

        self.assertEqual(list(MensagemTelegram.objects.all()), [com_json])
        com_json.refresh_from_db()
        self.assertIsNone(com_json.conteudo)

    def test_contadores_parados_saem_mas_bloqueio_valendo_fica(self):
        self.contador(1, dias_parado=8)
        ativo = self.contador(2, dias_parado=6)
        bloqueado = self.contador(3, dias_parado=8, bloqueado_ate=self.agora + timedelta(days=1))
        self.contador(4, dias_parado=8, bloqueado_ate=self.agora - timedelta(days=1))

        resultado = manutencao.limpar()

        self.assertEqual(set(LimiteTelegram.objects.values_list("pk", flat=True)), {ativo.pk, bloqueado.pk})
        self.assertEqual(resultado["contadores_apagados"], 2)

    def test_codigos_vencidos_saem(self):
        usuario = User.objects.create_user("ana", password="x")
        token_valido = CodigoVinculoTelegram.emitir(usuario)
        vencido = CodigoVinculoTelegram.objects.create(
            usuario=usuario, token_hash="vencido", expira_em=self.agora - timedelta(minutes=1),
        )

        resultado = manutencao.limpar()

        self.assertFalse(CodigoVinculoTelegram.objects.filter(pk=vencido.pk).exists())
        self.assertIsNotNone(CodigoVinculoTelegram.buscar_valido(token_valido))
        self.assertEqual(resultado["codigos_apagados"], 1)

    def test_lotes_pequenos_tratam_tudo(self):
        for _ in range(5):
            self.mensagem(61)
        for _ in range(5):
            self.mensagem(31, conteudo={"x": 1})

        resultado = manutencao.limpar(tamanho_lote=2)

        self.assertEqual(resultado["mensagens_apagadas"], 5)
        self.assertEqual(resultado["conteudos_apagados"], 5)

    def test_comando_mostra_o_resumo(self):
        self.mensagem(61)
        saida = StringIO()

        call_command("telegram_limpar", stdout=saida)

        self.assertIn("1 mensagens apagadas (mais antigas que 60 dias)", saida.getvalue())
        self.assertIn("contadores apagados (parados há mais de 7 dias)", saida.getvalue())


class RotaManutencaoTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        self.url = reverse("telegram:manutencao")
        antiga = MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.ENTRADA, situacao=MensagemTelegram.Situacao.PROCESSADA,
        )
        MensagemTelegram.objects.filter(pk=antiga.pk).update(criado_em=timezone.now() - timedelta(days=90))
        ambiente = mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": TAREFAS})
        ambiente.start()
        self.addCleanup(ambiente.stop)

    def test_segredo_certo_roda_a_limpeza(self):
        resposta = self.client.get(self.url, headers={"X-Tarefas-Segredo": TAREFAS})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["mensagens_apagadas"], 1)
        self.assertFalse(MensagemTelegram.objects.exists())

    def test_segredo_errado_ou_ausente_recusa(self):
        self.assertEqual(self.client.get(self.url, headers={"X-Tarefas-Segredo": "errado"}).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertTrue(MensagemTelegram.objects.exists())

    def test_sem_segredo_configurado_recusa(self):
        with mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": ""}):
            self.assertEqual(self.client.get(self.url, headers={"X-Tarefas-Segredo": ""}).status_code, 403)

    @override_settings(EM_PRODUCAO=True)
    def test_cron_do_app_engine_dispensa_o_segredo(self):
        resposta = self.client.get(self.url, headers={"X-Appengine-Cron": "true"})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(MensagemTelegram.objects.exists())

    def test_cabecalho_do_cron_fora_do_app_engine_nao_vale(self):
        # Fora do App Engine (ex.: pelo ngrok) qualquer um consegue mandar esse cabeçalho
        self.assertEqual(self.client.get(self.url, headers={"X-Appengine-Cron": "true"}).status_code, 403)

    def test_post_nao_e_aceito(self):
        resposta = self.client.post(self.url, headers={"X-Tarefas-Segredo": TAREFAS})

        self.assertEqual(resposta.status_code, 405)


class RotasSemRedirecionamentoTestCase(TestCase):
    """O Telegram e o cron não seguem redirecionamento: as duas rotas têm que responder direto."""
    RAIZ = Path(settings.BASE_DIR)

    def test_rotas_com_barra_no_fim_e_sem_login(self):
        self.assertEqual(reverse("telegram:webhook"), "/telegram/webhook/")
        self.assertEqual(reverse("telegram:manutencao"), "/telegram/manutencao/")

        with override_settings(TELEGRAM_WEBHOOK_SECRET=SEGREDO):
            webhook = self.client.post(reverse("telegram:webhook"), {}, content_type="application/json")
        manutencao_ = self.client.get(reverse("telegram:manutencao"))

        # Recusadas pelo segredo, mas respondidas na hora: nem login nem APPEND_SLASH no caminho
        self.assertEqual(webhook.status_code, 403)
        self.assertEqual(manutencao_.status_code, 403)

    def test_app_engine_nao_redireciona_a_manutencao(self):
        app_yaml = (self.RAIZ / "app.yaml").read_text(encoding="utf-8")
        manutencao_ = app_yaml.index("- url: /telegram/manutencao/")

        self.assertLess(manutencao_, app_yaml.index("- url: /.*"))  # o primeiro handler que casa é o que vale
        self.assertRegex(app_yaml[manutencao_:app_yaml.index("- url: /.*")], r"secure:\s*optional")

    def test_cron_chama_a_rota_de_manutencao(self):
        cron = (self.RAIZ / "cron.yaml").read_text(encoding="utf-8")

        self.assertRegex(cron, r"url:\s*" + re.escape(reverse("telegram:manutencao")))
