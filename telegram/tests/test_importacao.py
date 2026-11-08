from unittest import mock

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import override_settings

from ia.cota import CotaExcedida
from ia.models import ConfiguracaoIA
from importacao import services as importacao_services
from importacao.importadores import REGISTRO, Campo
from importacao.models import ConfiguracaoImportacao, Importacao
from importacao.tests.base import TIPO, ImportadorTeste, OutroImportador, png, resposta
from telegram import acoes, arquivos, importacoes, recebimento, signals
from telegram.models import AlbumTelegram, EsperaTelegram, ImportacaoTelegram

from .base import TELEGRAM_ANA, TELEGRAM_BIA, BotTestCase, clique, update

S = Importacao.Situacao
CORES = {1: "Azul", 2: "Verde"}


class ImportadorComCor(ImportadorTeste):
    """O importador de teste do app importacao, com um campo de escolha a mais."""

    def campos(self):
        return super().campos() + [Campo("cor", "Cor", "escolha", opcoes=lambda usuario: list(CORES.items()))]

    def resumo(self, dados):
        return super().resumo(dados) + [("Cor", CORES.get(dados.get("cor"), "—"))]

    def ajustar(self, dados, codigo, valor, usuario):
        if codigo == "cor":
            dados["cor"] = valor
            return dados, "Cor escolhida."
        return super().ajustar(dados, codigo, valor, usuario)


def foto(grande="foto-grande", **campos):
    """A mesma foto em dois tamanhos, como o Telegram manda."""
    return {"photo": [
        {"file_id": "foto-pequena", "file_unique_id": "p", "width": 90, "height": 90, "file_size": 1_000},
        {"file_id": grande, "file_unique_id": "g", "width": 800, "height": 600, "file_size": 50_000},
    ], **campos}


def botoes(chamada):
    return [botao.get("callback_data") or botao.get("url") for linha in chamada["reply_markup"]["inline_keyboard"] for botao in linha]


@override_settings(TAREFAS_BACKEND="imediata", SITE_URL="https://sigep.exemplo.com")
class ImportacaoPeloBotTestCase(BotTestCase):
    importadores = (ImportadorComCor,)

    def setUp(self):
        super().setUp()
        for chave in (ConfiguracaoIA.CHAVE_CACHE, ConfiguracaoImportacao.CHAVE_CACHE):
            cache.delete(chave)
        registro = mock.patch.dict(REGISTRO, {classe.tipo: classe() for classe in self.importadores}, clear=True)
        registro.start()
        self.addCleanup(registro.stop)
        patch = mock.patch("importacao.services.chamar_ia", return_value=resposta(nome="Equipe de vendas"))
        self.chamar_ia = patch.start()
        self.addCleanup(patch.stop)
        self.cliente.arquivos["foto-grande"] = png()
        self.vincular(self.ana, TELEGRAM_ANA)

    def mandar(self, texto=None, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            recebimento.receber(update(texto, update_id=self.novo_update_id(), **kwargs))

    def tocar(self, data, telegram_id=TELEGRAM_ANA):
        with self.captureOnCommitCallbacks(execute=True):
            recebimento.receber(clique(data, update_id=self.novo_update_id(), telegram_id=telegram_id))

    def chamadas(self, metodo):
        return [mensagem for mensagem in self.cliente.mensagens if mensagem["metodo"] == metodo]

    def resposta_do_botao(self):
        respostas = self.chamadas("answerCallbackQuery")
        self.assertEqual(len(respostas), 1)  # cada toque é respondido uma única vez
        return respostas[0]

    def importar(self, **campos):
        self.mandar(**foto(**campos))
        self.cliente.limpar()
        self.cliente.arquivos["foto-grande"] = png()
        return Importacao.objects.get()

    # ─── Chegada do arquivo ───────────────────────────────────────────────────

    def test_foto_vira_lendo_e_depois_o_cartao(self):
        self.mandar(caption="time do mês", **foto())

        importacao = Importacao.objects.get()
        self.assertEqual((importacao.situacao, importacao.origem, importacao.observacao), (S.PRONTA, "telegram", "time do mês"))
        lendo = self.chamadas("sendMessage")[0]
        self.assertEqual(lendo["text"], "🔎 Lendo o documento...")
        self.assertEqual(self.chamadas("getFile")[0]["file_id"], "foto-grande")  # a maior que cabe no limite

        cartao = self.chamadas("editMessageText")[-1]
        self.assertEqual(cartao["message_id"], 1)  # o "Lendo..." virou o cartão
        self.assertIn("Nome: Equipe de vendas", cartao["text"])
        self.assertEqual(botoes(cartao), [
            "ok:{}".format(importacao.pk), "ic:{}:nome".format(importacao.pk), "ic:{}:cor".format(importacao.pk),
            "https://sigep.exemplo.com/importacao/{}/revisar/".format(importacao.pk), "dc:{}".format(importacao.pk),
        ])
        vinculo = ImportacaoTelegram.objects.get()
        self.assertEqual((vinculo.file_id, vinculo.mensagem_bot_id, vinculo.chat_id), ("foto-grande", 1, TELEGRAM_ANA))

    def test_documento_de_tipo_errado_e_recusado_sem_abrir_importacao(self):
        self.mandar(document={"file_id": "d", "file_unique_id": "d", "mime_type": "text/plain", "file_size": 10})

        self.assertEqual(self.cliente.mensagens[-1]["text"], arquivos.TIPO_RECUSADO)
        self.assertFalse(Importacao.objects.exists())

    def test_pdf_e_aceito(self):
        self.cliente.arquivos["pdf"] = b"%PDF-1.4 nao e um pdf de verdade"
        self.mandar(document={"file_id": "pdf", "file_unique_id": "p", "mime_type": "application/pdf",
                              "file_name": "nota.pdf", "file_size": 30})

        importacao = Importacao.objects.get()
        self.assertEqual((importacao.arquivo_nome, importacao.arquivo_mime), ("nota.pdf", "application/pdf"))
        # O PDF de mentira não passa no preparar_arquivo: o cartão mostra a falha, sem a IA
        self.assertEqual(importacao.situacao, S.FALHOU)
        self.chamar_ia.assert_not_called()

    def test_album_vira_uma_importacao_e_um_aviso_so(self):
        for numero in range(3):
            self.mandar(**foto(grande="foto-grande", media_group_id="album-1"))

        self.assertEqual(Importacao.objects.count(), 1)
        avisos = [m for m in self.chamadas("sendMessage") if m["text"] == importacoes.AVISO_ALBUM]
        self.assertEqual(len(avisos), 1)
        self.assertTrue(AlbumTelegram.objects.get().avisado)

    def test_recusa_da_importacao_vai_para_a_pessoa(self):
        config = ConfiguracaoImportacao.obter()
        config.importacoes_por_hora = 1
        config.save()
        self.mandar(**foto())

        self.mandar(**foto())

        self.assertIn("1 documentos na última hora", self.cliente.mensagens[-1]["text"])
        self.assertEqual(Importacao.objects.count(), 1)

    def test_varios_importadores_perguntam_o_tipo_antes_de_baixar(self):
        with mock.patch.dict(REGISTRO, {"teste.outro": OutroImportador()}):
            self.mandar(**foto())
            importacao = Importacao.objects.get()
            pergunta = self.chamadas("sendMessage")[0]
            self.assertIn("O que é este documento?", pergunta["text"])
            self.assertIn("it:{}:{}".format(importacao.pk, TIPO), botoes(pergunta))
            self.assertEqual(self.chamadas("getFile"), [])

            self.tocar("it:{}:{}".format(importacao.pk, TIPO))

        importacao.refresh_from_db()
        self.assertEqual((importacao.tipo, importacao.situacao), (TIPO, S.PRONTA))
        self.assertIn("Nome: Equipe de vendas", self.chamadas("editMessageText")[-1]["text"])

    # ─── Falhas na leitura ────────────────────────────────────────────────────

    def test_cota_esgotada_mostra_sem_cota_e_tentar_de_novo(self):
        situacao_cota = mock.Mock()
        situacao_cota.mensagem_esgotada.return_value = "Sua cota de IA acabou. Ela renova em 01/12."
        self.chamar_ia.side_effect = CotaExcedida(situacao_cota)

        self.mandar(**foto())

        importacao = Importacao.objects.get()
        cartao = self.chamadas("editMessageText")[-1]
        self.assertEqual(importacao.situacao, S.BLOQUEADA)
        self.assertIn("Sua cota de IA acabou", cartao["text"])
        self.assertIn("tn:{}".format(importacao.pk), botoes(cartao))

        # A cota voltou: "Tentar de novo" baixa e lê de novo
        self.chamar_ia.side_effect = None
        self.cliente.limpar()
        self.cliente.arquivos["foto-grande"] = png()
        self.tocar("tn:{}".format(importacao.pk))

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PRONTA)
        self.assertEqual(self.chamadas("editMessageText")[0]["text"], "🔎 Lendo o documento...")
        self.assertIn("Equipe de vendas", self.chamadas("editMessageText")[-1]["text"])

    def test_falha_ao_baixar_mostra_tentar_de_novo(self):
        del self.cliente.arquivos["foto-grande"]

        self.mandar(**foto())

        importacao = Importacao.objects.get()
        self.assertEqual((importacao.situacao, importacao.mensagem_erro), (S.FALHOU, importacoes.MSG_DOWNLOAD))
        self.assertIn("tn:{}".format(importacao.pk), botoes(self.chamadas("editMessageText")[-1]))
        self.chamar_ia.assert_not_called()

    @override_settings(TAREFAS_BACKEND="desconhecido")
    def test_fila_recusando_mostra_o_cartao_com_tentar_de_novo(self):
        with self.assertLogs("importacao.tarefas", "ERROR"):
            self.mandar(**foto())

        importacao = Importacao.objects.get()
        self.assertEqual((importacao.situacao, importacao.mensagem_erro), (S.FALHOU, importacao_services.MSG_FILA))
        self.assertIn("tn:{}".format(importacao.pk), botoes(self.chamadas("editMessageText")[-1]))

    # ─── Botões do cartão ─────────────────────────────────────────────────────

    def test_confirmar_pelo_botao_cria_o_registro(self):
        importacao = self.importar()

        self.tocar("ok:{}".format(importacao.pk))

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.CONFIRMADA)
        self.assertEqual(importacao.objeto, Group.objects.get(name="Equipe de vendas"))
        edicoes = self.chamadas("editMessageText")
        self.assertEqual(len(edicoes), 1)  # o sinal não redesenha de novo o que o bot já mudou
        self.assertIn("Cadastrado!", edicoes[0]["text"])
        self.assertFalse(self.resposta_do_botao()["show_alert"])

    def test_confirmar_sem_o_obrigatorio_diz_qual_botao_resolve(self):
        self.chamar_ia.return_value = resposta(nome=None)
        importacao = self.importar()

        self.tocar("ok:{}".format(importacao.pk))

        alerta = self.resposta_do_botao()
        self.assertTrue(alerta["show_alert"])
        self.assertIn("Toque em ✏️ Nome", alerta["text"])
        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PRONTA)

    def test_botao_da_importacao_de_outra_pessoa_e_recusado(self):
        importacao = self.importar()
        self.vincular(self.bia, TELEGRAM_BIA)

        for data in ("ok:{}", "dc:{}", "tn:{}", "ic:{}:nome", "io:{}:cor:1", "ab:{}"):
            with self.subTest(data=data):
                self.cliente.limpar()
                self.tocar(data.format(importacao.pk), telegram_id=TELEGRAM_BIA)
                alerta = self.resposta_do_botao()
                self.assertEqual((alerta["text"], alerta["show_alert"]), (acoes.BOTAO_ANTIGO, True))

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PRONTA)
        self.assertFalse(Group.objects.filter(name="Equipe de vendas").exists())

    def test_descartar(self):
        importacao = self.importar()

        self.tocar("dc:{}".format(importacao.pk))

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.DESCARTADA)
        cartao = self.chamadas("editMessageText")[-1]
        self.assertIn("descartada", cartao["text"])
        self.assertNotIn("reply_markup", cartao)

    def test_corrigir_um_campo_por_texto(self):
        importacao = self.importar()

        self.tocar("ic:{}:nome".format(importacao.pk))
        pergunta = self.chamadas("editMessageText")[-1]
        self.assertIn("✏️ <b>Nome</b>", pergunta["text"])
        self.assertEqual(EsperaTelegram.objects.get().referencia, importacao)

        self.cliente.limpar()
        self.mandar("Time de vendas")

        importacao.refresh_from_db()
        self.assertEqual(importacao.dados["nome"], "Time de vendas")
        self.assertEqual(self.chamadas("deleteMessage")[0]["message_id"], 99)  # a pergunta (o cartão antigo)
        novo = self.chamadas("sendMessage")[-1]
        self.assertIn("✅ Nome alterado.", novo["text"])
        self.assertIn("Nome: Time de vendas", novo["text"])
        self.assertEqual(ImportacaoTelegram.objects.get().mensagem_bot_id, 1)  # o cartão novo passa a ser o vivo
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_texto_invalido_mantem_a_pergunta(self):
        importacao = self.importar()
        self.tocar("ic:{}:nome".format(importacao.pk))

        self.mandar("x" * 300)

        self.assertIn("até 200 caracteres", self.cliente.mensagens[-1]["text"])
        self.assertTrue(EsperaTelegram.objects.exists())

    def test_cancelar_a_pergunta_do_campo_devolve_o_cartao(self):
        importacao = self.importar()
        self.tocar("ic:{}:nome".format(importacao.pk))
        self.cliente.limpar()

        self.tocar("cx")

        self.assertIn("Nome: Equipe de vendas", self.chamadas("editMessageText")[-1]["text"])
        self.assertFalse(EsperaTelegram.objects.exists())

    def test_corrigir_um_campo_pela_lista(self):
        importacao = self.importar()

        self.tocar("ic:{}:cor".format(importacao.pk))
        lista = self.chamadas("editMessageText")[-1]
        self.assertIn("io:{}:cor:2".format(importacao.pk), botoes(lista))
        self.assertIn("iv:{}".format(importacao.pk), botoes(lista))

        self.tocar("io:{}:cor:2".format(importacao.pk))

        importacao.refresh_from_db()
        self.assertEqual(importacao.dados["cor"], 2)
        cartao = self.chamadas("editMessageText")[-1]
        self.assertIn("Cor: Verde", cartao["text"])
        self.assertIn("✅ Cor escolhida.", cartao["text"])

    def test_opcao_fora_da_lista_e_recusada(self):
        importacao = self.importar()

        self.tocar("io:{}:cor:99".format(importacao.pk))

        self.assertEqual(self.resposta_do_botao()["text"], acoes.BOTAO_ANTIGO)
        importacao.refresh_from_db()
        self.assertNotIn("cor", importacao.dados)

    def test_tentar_de_novo_do_que_veio_do_site_manda_para_o_site(self):
        importacao = Importacao.objects.create(criado_por=self.ana, tipo=TIPO, situacao=S.FALHOU)

        self.tocar("tn:{}".format(importacao.pk))

        self.assertIn("enviado pelo site", self.resposta_do_botao()["text"])
        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.FALHOU)

    # ─── /pendentes e sinal ───────────────────────────────────────────────────

    def test_pendentes_lista_e_reabre_o_cartao_no_fim_do_chat(self):
        importacao = self.importar()
        Importacao.objects.create(criado_por=self.bia, tipo=TIPO, situacao=S.PRONTA)  # de outra pessoa

        self.mandar("/pendentes")
        lista = self.cliente.mensagens[-1]
        self.assertIn("1 importação", lista["text"])
        self.assertEqual(botoes(lista), ["ab:{}".format(importacao.pk)])

        self.cliente.limpar()
        self.tocar("ab:{}".format(importacao.pk))

        self.assertIn("Nome: Equipe de vendas", self.chamadas("sendMessage")[0]["text"])
        self.assertEqual(self.chamadas("deleteMessage")[0]["message_id"], 1)  # o cartão antigo
        self.assertEqual(ImportacaoTelegram.objects.get().mensagem_bot_id, 1)

    def test_pendentes_sem_nada(self):
        self.mandar("/pendentes")

        self.assertIn("Nenhuma importação para revisar", self.cliente.mensagens[-1]["text"])

    def test_confirmacao_no_site_redesenha_o_cartao(self):
        importacao = self.importar()

        with self.captureOnCommitCallbacks(execute=True):
            importacao_services.confirmar_importacao(importacao, self.ana, "site")

        cartao = self.chamadas("editMessageText")[-1]
        self.assertEqual(cartao["message_id"], 1)
        self.assertTrue(cartao["text"].startswith(signals.AVISO_SITE))
        self.assertIn("Cadastrado!", cartao["text"])

    def test_cartao_apagado_vai_como_mensagem_nova(self):
        importacao = self.importar()
        self.cliente.programar("editMessageText", None)

        with self.captureOnCommitCallbacks(execute=True):
            importacao_services.descartar_importacao(importacao, self.ana, "site")

        self.assertIn("descartada", self.chamadas("sendMessage")[-1]["text"])
        self.assertEqual(ImportacaoTelegram.objects.get().mensagem_bot_id, 1)

    def test_falha_ao_avisar_o_telegram_nao_derruba_o_site(self):
        importacao = self.importar()

        with mock.patch("telegram.importacoes.atualizar_cartao", side_effect=RuntimeError("Telegram fora")):
            with self.assertLogs("telegram.signals", "ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    importacao_services.confirmar_importacao(importacao, self.ana, "site")

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.CONFIRMADA)


class EscolherMidiaTestCase(BotTestCase):

    def setUp(self):
        super().setUp()
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        config = ConfiguracaoIA.obter()
        config.tamanho_maximo_mb = 1
        config.save()

    def test_maior_foto_dentro_do_limite(self):
        fotos = {"photo": [
            {"file_id": "p", "width": 90, "height": 90, "file_size": 1_000},
            {"file_id": "m", "width": 800, "height": 600, "file_size": 500_000},
            {"file_id": "g", "width": 2000, "height": 1500, "file_size": 2_000_000},
        ]}

        self.assertEqual(arquivos.escolher_midia(fotos)["file_id"], "m")

    def test_foto_toda_acima_do_limite_e_recusada(self):
        recusa = arquivos.escolher_midia({"photo": [{"file_id": "g", "width": 10, "height": 10, "file_size": 3 * 1024 * 1024}]})

        self.assertEqual(recusa, "O arquivo tem 3,0 MB e o limite é 1 MB. Envie um arquivo menor.")

    def test_documentos_aceitos_e_recusados(self):
        def documento(mime, tamanho=100):
            return {"document": {"file_id": "d", "mime_type": mime, "file_size": tamanho, "file_name": "x"}}

        for mime in ("image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"):
            with self.subTest(mime=mime):
                self.assertEqual(arquivos.escolher_midia(documento(mime))["mime"], mime)
        self.assertEqual(arquivos.escolher_midia(documento("application/zip")), arquivos.TIPO_RECUSADO)
        self.assertIn("limite é 1 MB", arquivos.escolher_midia(documento("application/pdf", 2 * 1024 * 1024)))

    def test_nunca_acima_dos_20_mb_do_get_file(self):
        config = ConfiguracaoIA.obter()
        config.tamanho_maximo_mb = 50
        config.save()

        self.assertEqual(arquivos.limite_bytes(), 20 * 1024 * 1024)
        recusa = arquivos.escolher_midia({"document": {"file_id": "d", "mime_type": "application/pdf", "file_size": 25 * 1024 * 1024}})
        self.assertIn("limite é 20 MB", recusa)
