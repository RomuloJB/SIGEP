from datetime import date, timedelta
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from telegram import acoes, comandos, conversa, entradas, limites, recebimento, roteador, telas
from telegram.models import (
    CodigoVinculoTelegram, ConfiguracaoTelegram, EsperaTelegram, LimiteTelegram, MensagemTelegram, VinculoTelegram,
)
from telegram.views import CABECALHO_SEGREDO

from .base import TELEGRAM_ANA, TELEGRAM_BIA, BotTestCase, clique, pessoa, update

SEGREDO = "segredo-do-webhook"
TOKEN = "123456:TOKEN-secreto_do_bot"
FOTO = {"photo": [{"file_id": "abc", "file_unique_id": "u", "width": 90, "height": 90}]}
DOCUMENTO = {"document": {"file_id": "abc", "file_unique_id": "u"}}


@override_settings(TELEGRAM_WEBHOOK_SECRET=SEGREDO)
class WebhookTestCase(BotTestCase):

    def postar(self, corpo, segredo=SEGREDO):
        cabecalhos = {} if segredo is None else {CABECALHO_SEGREDO: segredo}
        return self.client.post(reverse("telegram:webhook"), corpo, content_type="application/json", headers=cabecalhos)

    def entradas(self):
        return MensagemTelegram.objects.filter(direcao=MensagemTelegram.Direcao.ENTRADA)

    def envelhecer(self, segundos):
        self.entradas().update(criado_em=timezone.now() - timedelta(seconds=segundos))

    def test_conecta_de_ponta_a_ponta(self):
        resposta = self.postar(update("/start {}".format(CodigoVinculoTelegram.emitir(self.ana))))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(VinculoTelegram.objects.get().usuario, self.ana)
        self.assertIn("✅ Conectado", self.cliente.mensagens[-1]["text"])
        self.assertEqual(self.entradas().get().situacao, MensagemTelegram.Situacao.PROCESSADA)

    def test_segredo_errado_ou_ausente_devolve_403(self):
        for segredo in ("errado", None, ""):
            with self.subTest(segredo=segredo):
                self.assertEqual(self.postar(update("/start"), segredo=segredo).status_code, 403)
        self.assertFalse(MensagemTelegram.objects.exists())

    @override_settings(TELEGRAM_WEBHOOK_SECRET="")
    def test_sem_segredo_configurado_devolve_503(self):
        for segredo in ("qualquer", "", None):
            with self.subTest(segredo=segredo):
                self.assertEqual(self.postar(update("/start"), segredo=segredo).status_code, 503)
        self.assertFalse(MensagemTelegram.objects.exists())

    def test_corpo_invalido_devolve_400(self):
        for corpo in ("isto não é json", "[1, 2]", {"message": {}}, {"update_id": "1"}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.postar(corpo).status_code, 400)

    def test_get_nao_e_aceito(self):
        self.assertEqual(self.client.get(reverse("telegram:webhook")).status_code, 405)

    def test_update_repetido_e_processado_uma_vez(self):
        self.postar(update("/start", update_id=7))
        resposta = self.postar(update("/start", update_id=7))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(self.cliente.mensagens), 1)
        self.assertEqual(self.entradas().filter(update_id=7).count(), 1)

    def test_recebida_antiga_e_reprocessada_por_um_unico_reenvio(self):
        with mock.patch("telegram.roteador.processar"):  # a instância "caiu": ficou em recebida
            self.postar(update("/start", update_id=7))
        self.envelhecer(121)

        self.postar(update("/start", update_id=7))
        self.postar(update("/start", update_id=7))

        self.assertEqual(len(self.cliente.mensagens), 1)
        self.assertEqual(self.entradas().get().situacao, MensagemTelegram.Situacao.PROCESSADA)
        self.assertEqual(self.entradas().get().erro, "")

    def test_reprocessamento_que_cai_de_novo_nao_tem_outra_chance(self):
        with mock.patch("telegram.roteador.processar"):
            self.postar(update("/start", update_id=7))
        self.envelhecer(121)
        with mock.patch("telegram.roteador.processar"):
            self.postar(update("/start", update_id=7))
        self.envelhecer(121)

        self.postar(update("/start", update_id=7))

        self.assertEqual(self.cliente.mensagens, [])
        self.assertEqual(self.entradas().get().situacao, MensagemTelegram.Situacao.ERRO)
        self.assertEqual(self.entradas().get().erro, recebimento.INTERROMPIDA)

    def test_recebida_recente_nao_e_reprocessada(self):
        with mock.patch("telegram.roteador.processar"):
            self.postar(update("/start", update_id=7))
        self.envelhecer(119)

        self.postar(update("/start", update_id=7))

        self.assertEqual(self.cliente.mensagens, [])
        self.assertEqual(self.entradas().get().situacao, MensagemTelegram.Situacao.RECEBIDA)

    def test_processada_antiga_nao_e_reprocessada(self):
        self.postar(update("/start", update_id=7))
        self.envelhecer(121)

        self.postar(update("/start", update_id=7))

        self.assertEqual(len(self.cliente.mensagens), 1)

    def test_o_que_o_bot_nao_atende_nao_grava_nada(self):
        do_bot = update("oi")
        do_bot["message"]["from"]["is_bot"] = True
        sem_remetente = update("oi")
        del sem_remetente["message"]["from"]
        casos = {
            "grupo": update("/start", tipo_chat="group"),
            "supergrupo": update("/start", tipo_chat="supergroup"),
            "canal": update("/start", tipo_chat="channel"),
            "bot": do_bot,
            "sem remetente": sem_remetente,
            "postagem de canal": {"update_id": 1, "channel_post": {"chat": {"id": 1, "type": "channel"}, "text": "oi"}},
            "mensagem editada": {"update_id": 1, "edited_message": {"from": pessoa(), "text": "/start abc"}},
            "botão em grupo": clique("ok:1", tipo_chat="group"),
        }
        for nome, corpo in casos.items():
            with self.subTest(nome):
                self.assertEqual(self.postar(corpo).status_code, 200)
                self.assertFalse(MensagemTelegram.objects.exists())
                self.assertFalse(LimiteTelegram.objects.exists())
                self.assertEqual(self.cliente.mensagens, [])

    def test_excecao_no_roteador_devolve_200_avisa_e_registra(self):
        with self.assertLogs("telegram.recebimento", level="ERROR"):
            with mock.patch("telegram.roteador.processar", side_effect=RuntimeError("falhou")):
                resposta = self.postar(update("/start"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.cliente.mensagens[-1]["text"], recebimento.ERRO_GENERICO)
        entrada = self.entradas().get()
        self.assertEqual(entrada.situacao, MensagemTelegram.Situacao.ERRO)
        self.assertIn("RuntimeError: falhou", entrada.erro)

    def test_aviso_de_erro_sai_no_maximo_a_cada_10_minutos(self):
        with self.assertLogs("telegram.recebimento", level="ERROR"):
            with mock.patch("telegram.roteador.processar", side_effect=RuntimeError("falhou")):
                self.postar(update("/start", update_id=1))
                self.postar(update("/start", update_id=2))
                self.assertEqual(len(self.cliente.mensagens), 1)

                LimiteTelegram.objects.update(erro_avisado_em=timezone.now() - timedelta(minutes=10, seconds=1))
                self.postar(update("/start", update_id=3))

        self.assertEqual(len(self.cliente.mensagens), 2)
        self.assertEqual(self.entradas().filter(situacao=MensagemTelegram.Situacao.ERRO).count(), 3)

    def test_json_so_de_quem_esta_vinculado(self):
        self.postar(update("/start", update_id=1))
        self.vincular(self.ana, TELEGRAM_ANA)
        self.postar(update("/start", update_id=2))

        self.assertIsNone(self.entradas().get(update_id=1).conteudo)
        self.assertEqual(self.entradas().get(update_id=2).conteudo["update_id"], 2)

    @override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
    def test_log_nunca_guarda_o_token_nem_o_codigo(self):
        self.vincular(self.ana, TELEGRAM_ANA)
        codigo = CodigoVinculoTelegram.emitir(self.bia)

        self.postar(update("meu token é {}".format(TOKEN), update_id=1))
        self.postar(update("/start {}".format(codigo), update_id=2))

        guardado = str(list(MensagemTelegram.objects.values()))
        self.assertNotIn(TOKEN, guardado)
        self.assertNotIn(codigo, guardado)
        self.assertEqual(self.entradas().get(update_id=2).conteudo["message"]["text"], "/start ***")

    def test_botao_entra_no_log_como_botao(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.postar(clique("ok:45", update_id=9))

        entrada = self.entradas().get()
        self.assertEqual(entrada.tipo, "botao")
        self.assertEqual(entrada.texto, "ok:45")
        self.assertEqual(entrada.chat_id, TELEGRAM_ANA)

    def test_arquivo_entra_no_log_como_arquivo_com_a_legenda(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.postar(update(update_id=9, caption="nota de maio", **DOCUMENTO))

        entrada = self.entradas().get()
        self.assertEqual(entrada.tipo, "arquivo")
        self.assertEqual(entrada.texto, "nota de maio")


@override_settings(SITE_URL="https://sigep.exemplo.com")
class RoteadorTestCase(BotTestCase):

    def clicar(self, data):
        recebimento.receber(clique(data, update_id=self.novo_update_id()))
        return self.cliente.mensagens[-1]

    def esperar(self, vinculo, campo="data"):
        return EsperaTelegram.objects.create(vinculo=vinculo, campo=campo)

    def test_botao_vai_para_a_acao_registrada(self):
        vinculo = self.vincular(self.ana, TELEGRAM_ANA)
        acao = mock.Mock(return_value=None)

        with mock.patch.dict(acoes.ACOES, {"ok": acao}):
            recebimento.receber(clique("ok:45", update_id=1))

        recebido, argumento, callback = acao.call_args.args
        self.assertEqual(callback["data"], "ok:45")
        self.assertEqual(argumento, "45")
        self.assertEqual(recebido, vinculo)

    def test_botao_vem_antes_de_tudo(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA))

        with mock.patch("telegram.roteador.acoes.despachar") as despachar:
            with mock.patch("telegram.roteador.conversa.receber_texto") as receber_texto:
                recebimento.receber(clique("ok:1", update_id=1))

        despachar.assert_called_once()
        receber_texto.assert_not_called()

    def test_botao_sem_acao_responde_para_nao_ficar_carregando(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        resposta = self.clicar("nao-existe:1")

        self.assertEqual(resposta["metodo"], "answerCallbackQuery")
        self.assertEqual(resposta["text"], acoes.BOTAO_ANTIGO)
        self.assertTrue(resposta["show_alert"])

    def test_botao_de_quem_nao_esta_conectado_nao_roda_a_acao(self):
        acao = mock.Mock()

        with mock.patch.dict(acoes.ACOES, {"ok": acao}):
            resposta = self.clicar("ok:1")

        acao.assert_not_called()
        self.assertEqual(resposta["metodo"], "answerCallbackQuery")

    def test_comando_vem_antes_da_espera(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA))

        with mock.patch("telegram.roteador.conversa.receber_texto") as receber_texto:
            resposta = self.enviar("/start")

        receber_texto.assert_not_called()
        self.assertIn(comandos.BOAS_VINDAS, resposta["text"])

    def test_cancelar_apaga_a_espera_sem_tratar_como_resposta(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA))

        with mock.patch("telegram.roteador.conversa.receber_texto") as receber_texto:
            resposta = self.enviar("/cancelar")

        receber_texto.assert_not_called()
        self.assertEqual(resposta["text"], comandos.CANCELADO)
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_cancelar_sem_espera(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.assertEqual(self.enviar("/cancelar")["text"], comandos.NADA_PARA_CANCELAR)

    def test_comando_desconhecido_cai_na_ajuda_e_nao_responde_a_espera(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA))

        with mock.patch("telegram.roteador.conversa.receber_texto") as receber_texto:
            resposta = self.enviar("/nao-existe")

        receber_texto.assert_not_called()
        self.assertEqual(resposta["text"], comandos.AJUDA)

    def test_sem_vinculo_recebe_o_aviso_com_botao_para_o_site(self):
        resposta = self.enviar("bom dia")

        self.assertEqual(resposta["text"], comandos.COMO_CONECTAR)
        self.assertEqual(
            resposta["reply_markup"]["inline_keyboard"][0][0]["url"],
            "https://sigep.exemplo.com" + reverse("telegram:conexao"),
        )

    @override_settings(SITE_URL="http://127.0.0.1:8000")
    def test_aviso_sem_https_vai_sem_o_botao(self):
        resposta = self.enviar("bom dia")

        self.assertEqual(resposta["text"], comandos.COMO_CONECTAR)
        self.assertNotIn("reply_markup", resposta)

    def test_arquivo_de_quem_nao_esta_conectado_recebe_o_aviso(self):
        self.assertEqual(self.enviar(**FOTO)["text"], comandos.COMO_CONECTAR)

    def test_comando_desconhecido_de_quem_nao_esta_conectado_recebe_o_aviso(self):
        self.assertEqual(self.enviar("/nao-existe")["text"], comandos.COMO_CONECTAR)

    def test_foto_e_documento_ainda_nao_tem_uso(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.assertEqual(self.enviar(**FOTO)["text"], roteador.ARQUIVO_SEM_USO)
        self.assertEqual(self.enviar(**DOCUMENTO)["text"], roteador.ARQUIVO_SEM_USO)

    def test_arquivo_vem_antes_da_espera_e_cancela_a_espera(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA))

        with mock.patch("telegram.roteador.conversa.receber_texto") as receber_texto:
            resposta = self.enviar(caption="legenda", **FOTO)

        receber_texto.assert_not_called()
        self.assertEqual(resposta["text"], roteador.ARQUIVO_SEM_USO)
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_texto_com_espera_ativa_vira_a_resposta(self):
        vinculo = self.vincular(self.ana, TELEGRAM_ANA)
        self.esperar(vinculo)
        responder = mock.Mock(return_value=telas.Tela("Data anotada."))
        campo = conversa.CampoTexto("Qual a data?", entradas.interpretar_data, responder)

        with mock.patch.dict(conversa.CAMPOS_TEXTO, {"data": campo}):
            resposta = self.enviar("31/12/2026")

        recebido, valor = responder.call_args.args
        self.assertEqual(recebido, vinculo)
        self.assertEqual(valor, date(2026, 12, 31))
        self.assertEqual(resposta["text"], "Data anotada.")
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_espera_sem_tratador_nao_prende_a_pessoa(self):
        self.esperar(self.vincular(self.ana, TELEGRAM_ANA), campo="antigo")

        resposta = self.enviar("31/12/2026")

        self.assertEqual(resposta["text"], conversa.PERGUNTA_SEM_USO)
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_o_resto_recebe_a_ajuda(self):
        self.vincular(self.ana, TELEGRAM_ANA)

        self.assertEqual(self.enviar("bom dia")["text"], comandos.AJUDA)
        self.assertEqual(self.enviar(sticker={"file_id": "abc"})["text"], comandos.AJUDA)

    def test_uso_e_gravado_no_maximo_uma_vez_por_minuto(self):
        vinculo = self.vincular(self.ana, TELEGRAM_ANA)
        faz_tempo = timezone.now() - timedelta(seconds=61)
        VinculoTelegram.objects.filter(pk=vinculo.pk).update(ultimo_uso=faz_tempo, chat_id=1)

        self.enviar("bom dia")

        vinculo.refresh_from_db()
        gravado = vinculo.ultimo_uso
        self.assertGreater(gravado, faz_tempo)
        self.assertEqual(vinculo.chat_id, TELEGRAM_ANA)

        self.enviar("bom dia")

        vinculo.refresh_from_db()
        self.assertEqual(vinculo.ultimo_uso, gravado)


class LimitesConectadoTestCase(BotTestCase):

    def setUp(self):
        super().setUp()
        self.vincular(self.ana, TELEGRAM_ANA)

    def limite(self):
        return LimiteTelegram.objects.get(telegram_id=TELEGRAM_ANA)

    def entradas(self):
        return MensagemTelegram.objects.filter(direcao=MensagemTelegram.Direcao.ENTRADA).count()

    def encerrar_janela(self):
        LimiteTelegram.objects.update(janela_inicio=timezone.now() - timedelta(seconds=61))

    def test_acima_de_20_mensagens_recebe_um_aviso_e_pausa_5_minutos(self):
        for _ in range(20):
            self.assertEqual(self.enviar("oi")["text"], comandos.AJUDA)

        resposta = self.enviar("oi")

        self.assertEqual(resposta["text"], limites.AVISO_PAUSA.format(5))
        restante = self.limite().bloqueado_ate - timezone.now()
        self.assertGreater(restante, timedelta(minutes=4, seconds=50))
        self.assertLessEqual(restante, timedelta(minutes=5))

    def test_durante_a_pausa_nao_responde_nem_grava(self):
        for _ in range(21):
            self.enviar("oi")
        respostas = len(self.cliente.mensagens)

        self.enviar("oi")
        self.enviar("/start")

        self.assertEqual(len(self.cliente.mensagens), respostas)
        self.assertEqual(self.entradas(), 20)
        self.assertEqual(self.limite().total, 23)
        self.assertEqual(self.limite().descartadas, 3)

    def test_depois_da_pausa_volta_ao_normal(self):
        for _ in range(21):
            self.enviar("oi")
        LimiteTelegram.objects.update(bloqueado_ate=timezone.now() - timedelta(seconds=1))
        self.encerrar_janela()

        self.assertEqual(self.enviar("oi")["text"], comandos.AJUDA)
        self.assertEqual(self.limite().mensagens, 1)

    def test_janela_nova_zera_a_contagem(self):
        for _ in range(20):
            self.enviar("oi")
        self.encerrar_janela()

        self.assertEqual(self.enviar("oi")["text"], comandos.AJUDA)
        self.assertIsNone(self.limite().bloqueado_ate)

    def test_acima_de_4_arquivos_recusa_os_extras_com_um_aviso_so(self):
        for _ in range(4):
            self.assertEqual(self.enviar(**FOTO)["text"], roteador.ARQUIVO_SEM_USO)

        self.assertEqual(self.enviar(**FOTO)["text"], limites.AVISO_ARQUIVOS)
        respostas = len(self.cliente.mensagens)
        self.enviar(**DOCUMENTO)

        self.assertEqual(len(self.cliente.mensagens), respostas)
        self.assertEqual(self.entradas(), 4)

    def test_limite_de_arquivos_nao_pausa_as_mensagens(self):
        for _ in range(5):
            self.enviar(**FOTO)

        self.assertEqual(self.enviar("oi")["text"], comandos.AJUDA)
        self.assertIsNone(self.limite().bloqueado_ate)

    def test_janela_nova_volta_a_aceitar_arquivos_e_a_avisar(self):
        for _ in range(5):
            self.enviar(**FOTO)
        self.encerrar_janela()

        self.assertEqual(self.enviar(**FOTO)["text"], roteador.ARQUIVO_SEM_USO)
        for _ in range(3):
            self.enviar(**FOTO)
        self.assertEqual(self.enviar(**FOTO)["text"], limites.AVISO_ARQUIVOS)

    def test_mensagem_de_um_botao_nao_conta_como_arquivo(self):
        atualizacao = clique("ok:1")
        atualizacao["callback_query"]["message"].update(FOTO)

        recebimento.receber(atualizacao)

        self.assertEqual(self.limite().arquivos, 0)
        self.assertEqual(self.limite().mensagens, 1)

    def test_usa_os_numeros_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.mensagens_por_minuto = 2
        config.bloqueio_minutos = 9
        config.save()

        self.enviar("oi")
        self.enviar("oi")

        self.assertEqual(self.enviar("oi")["text"], limites.AVISO_PAUSA.format(9))

    def test_arquivos_usam_o_numero_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.arquivos_por_minuto = 1
        config.save()

        self.enviar(**FOTO)

        self.assertEqual(self.enviar(**FOTO)["text"], limites.AVISO_ARQUIVOS)


class LimitesDesconhecidoTestCase(BotTestCase):

    def limite(self):
        return LimiteTelegram.objects.get(telegram_id=TELEGRAM_BIA)

    def enviar_da_bia(self, texto=None, **kwargs):
        return self.enviar(texto, telegram_id=TELEGRAM_BIA, **kwargs)

    def test_acima_de_5_por_minuto_ignora_por_60_minutos_sem_avisar(self):
        for _ in range(5):
            self.enviar_da_bia("/start")
        respostas = len(self.cliente.mensagens)

        self.enviar_da_bia("/start")

        self.assertEqual(len(self.cliente.mensagens), respostas)
        restante = self.limite().bloqueado_ate - timezone.now()
        self.assertGreater(restante, timedelta(minutes=59, seconds=50))
        self.assertLessEqual(restante, timedelta(minutes=60))

    def test_ignorado_nao_grava_no_log(self):
        for _ in range(7):
            self.enviar_da_bia("/start")

        self.assertEqual(MensagemTelegram.objects.filter(direcao=MensagemTelegram.Direcao.ENTRADA).count(), 5)
        self.assertEqual(self.limite().total, 7)
        self.assertEqual(self.limite().descartadas, 2)

    def test_depois_do_prazo_volta_a_ser_atendido(self):
        for _ in range(6):
            self.enviar_da_bia("/start")
        LimiteTelegram.objects.update(
            bloqueado_ate=timezone.now() - timedelta(seconds=1), janela_inicio=timezone.now() - timedelta(seconds=61),
        )
        respostas = len(self.cliente.mensagens)

        self.enviar_da_bia("/start")

        self.assertEqual(len(self.cliente.mensagens), respostas + 1)

    def test_ja_avisado_nao_recebe_resposta_nem_entra_no_log(self):
        self.assertEqual(self.enviar_da_bia("oi")["text"], comandos.COMO_CONECTAR)

        self.enviar_da_bia("oi")
        self.enviar_da_bia(**FOTO)

        self.assertEqual(len(self.cliente.mensagens), 1)
        self.assertEqual(MensagemTelegram.objects.filter(direcao=MensagemTelegram.Direcao.ENTRADA).count(), 1)
        self.assertEqual(self.limite().descartadas, 2)

    def test_aviso_volta_depois_de_12_horas(self):
        self.enviar_da_bia("oi")
        LimiteTelegram.objects.update(
            aviso_em=timezone.now() - timedelta(hours=12, seconds=1), janela_inicio=timezone.now() - timedelta(seconds=61),
        )

        self.enviar_da_bia("oi")

        self.assertEqual(len(self.cliente.mensagens), 2)

    def test_aviso_nao_volta_antes_de_12_horas(self):
        self.enviar_da_bia("oi")
        LimiteTelegram.objects.update(
            aviso_em=timezone.now() - timedelta(hours=11, minutes=59), janela_inicio=timezone.now() - timedelta(seconds=61),
        )

        self.enviar_da_bia("oi")

        self.assertEqual(len(self.cliente.mensagens), 1)

    def test_ja_avisado_ainda_consegue_se_conectar(self):
        # O caminho normal: recebe o aviso, gera o código no site e toca no link
        self.enviar_da_bia("oi")
        token = CodigoVinculoTelegram.emitir(self.bia)

        resposta = self.enviar_da_bia("/start {}".format(token))

        self.assertIn("✅ Conectado", resposta["text"])
        self.assertEqual(VinculoTelegram.objects.get().usuario, self.bia)

    def test_comando_desconhecido_de_quem_ja_foi_avisado_nao_repete_o_aviso(self):
        self.enviar_da_bia("oi")

        self.enviar_da_bia("/nao-existe")

        self.assertEqual(len(self.cliente.mensagens), 1)

    def test_bloqueado_nao_conecta_ate_ser_liberado(self):
        for _ in range(6):
            self.enviar_da_bia("/start")
        token = CodigoVinculoTelegram.emitir(self.bia)

        self.enviar_da_bia("/start {}".format(token))
        self.assertFalse(VinculoTelegram.objects.exists())

        limites.liberar(self.limite())
        self.enviar_da_bia("/start {}".format(token))
        self.assertEqual(VinculoTelegram.objects.get().usuario, self.bia)

    def test_usuario_desativado_conta_como_desconhecido(self):
        self.vincular(self.bia, TELEGRAM_BIA)
        self.bia.is_active = False
        self.bia.save()

        for _ in range(6):
            self.enviar_da_bia("/start")

        self.assertTrue(self.limite().bloqueado)

    def test_usa_os_numeros_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.desconhecido_mensagens_por_minuto = 1
        config.desconhecido_bloqueio_minutos = 2
        config.save()

        self.enviar_da_bia("/start")
        self.enviar_da_bia("/start")

        self.assertLessEqual(self.limite().bloqueado_ate - timezone.now(), timedelta(minutes=2))

    def test_aviso_usa_o_numero_da_configuracao(self):
        config = ConfiguracaoTelegram.obter()
        config.desconhecido_aviso_horas = 1
        config.save()
        self.enviar_da_bia("oi")
        LimiteTelegram.objects.update(aviso_em=timezone.now() - timedelta(hours=1, seconds=1))

        self.enviar_da_bia("oi")

        self.assertEqual(len(self.cliente.mensagens), 2)

    def test_cada_remetente_tem_o_seu_contador(self):
        for _ in range(6):
            self.enviar_da_bia("/start")

        self.assertIn(comandos.BOAS_VINDAS, self.enviar("/start")["text"])


class AvisosTestCase(BotTestCase):

    def test_duas_chamadas_seguidas_so_uma_pode_avisar(self):
        LimiteTelegram.objects.create(telegram_id=TELEGRAM_ANA)

        self.assertTrue(limites.pode_avisar_conexao(TELEGRAM_ANA))
        self.assertFalse(limites.pode_avisar_conexao(TELEGRAM_ANA))
        self.assertTrue(limites.pode_avisar_erro(TELEGRAM_ANA))
        self.assertFalse(limites.pode_avisar_erro(TELEGRAM_ANA))

    def test_liberar_zera_a_janela_para_nao_bloquear_de_novo(self):
        limite = LimiteTelegram.objects.create(
            telegram_id=TELEGRAM_ANA, mensagens=50, arquivos=9, avisou_arquivos=True, total=60, descartadas=10,
            janela_inicio=timezone.now(), bloqueado_ate=timezone.now() + timedelta(minutes=5),
        )

        limites.liberar(limite)

        limite.refresh_from_db()
        self.assertFalse(limite.bloqueado)
        self.assertEqual((limite.mensagens, limite.arquivos, limite.avisou_arquivos), (0, 0, False))
        self.assertEqual((limite.total, limite.descartadas), (60, 10))
