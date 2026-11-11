import logging
import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from telegram.models import (
    CodigoVinculoTelegram, ConfiguracaoTelegram, EsperaTelegram, LimiteTelegram, MensagemTelegram, VinculoTelegram,
)

ID_GRANDE = 9_000_000_000  # não cabe num IntegerField comum


class CodigoVinculoTelegramTestCase(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user("ana", password="x")

    def test_emitir_grava_so_o_hash(self):
        token = CodigoVinculoTelegram.emitir(self.usuario)

        codigo = CodigoVinculoTelegram.objects.get()
        self.assertEqual(codigo.token_hash, CodigoVinculoTelegram.calcular_hash(token))
        self.assertNotEqual(codigo.token_hash, token)
        self.assertNotIn(token, str(CodigoVinculoTelegram.objects.values().first()))

    def test_token_cabe_no_link_do_telegram(self):
        # O parâmetro start aceita até 64 caracteres: letras, números, _ e -
        self.assertRegex(CodigoVinculoTelegram.emitir(self.usuario), re.compile(r"^[A-Za-z0-9_-]{1,64}$"))

    def test_validade_de_15_minutos(self):
        antes = timezone.now()
        CodigoVinculoTelegram.emitir(self.usuario)

        restante = CodigoVinculoTelegram.objects.get().expira_em - antes
        self.assertGreaterEqual(restante, timedelta(minutes=15))
        self.assertLess(restante, timedelta(minutes=15, seconds=30))

    def test_buscar_valido_encontra_o_codigo(self):
        token = CodigoVinculoTelegram.emitir(self.usuario)

        self.assertEqual(CodigoVinculoTelegram.buscar_valido(token).usuario, self.usuario)

    def test_buscar_valido_recusa_token_desconhecido_ou_vazio(self):
        CodigoVinculoTelegram.emitir(self.usuario)

        self.assertIsNone(CodigoVinculoTelegram.buscar_valido("nao-existe"))
        self.assertIsNone(CodigoVinculoTelegram.buscar_valido(""))
        self.assertIsNone(CodigoVinculoTelegram.buscar_valido(None))

    def test_codigo_usado_nao_vale(self):
        token = CodigoVinculoTelegram.emitir(self.usuario)
        CodigoVinculoTelegram.objects.update(usado_em=timezone.now())

        self.assertIsNone(CodigoVinculoTelegram.buscar_valido(token))

    def test_codigo_vencido_nao_vale(self):
        token = CodigoVinculoTelegram.emitir(self.usuario)
        CodigoVinculoTelegram.objects.update(expira_em=timezone.now() - timedelta(seconds=1))

        self.assertIsNone(CodigoVinculoTelegram.buscar_valido(token))

    def test_codigo_novo_invalida_o_anterior(self):
        anterior = CodigoVinculoTelegram.emitir(self.usuario)
        novo = CodigoVinculoTelegram.emitir(self.usuario)

        self.assertIsNone(CodigoVinculoTelegram.buscar_valido(anterior))
        self.assertIsNotNone(CodigoVinculoTelegram.buscar_valido(novo))

    def test_codigo_novo_nao_mexe_no_de_outro_usuario(self):
        outro = User.objects.create_user("bia", password="x")
        token_do_outro = CodigoVinculoTelegram.emitir(outro)

        CodigoVinculoTelegram.emitir(self.usuario)

        self.assertEqual(CodigoVinculoTelegram.buscar_valido(token_do_outro).usuario, outro)


class VinculoTelegramTestCase(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user("ana", password="x")

    def test_guarda_ids_acima_de_2_bilhoes(self):
        vinculo = VinculoTelegram.objects.create(usuario=self.usuario, telegram_id=ID_GRANDE, chat_id=ID_GRANDE + 1)

        vinculo.refresh_from_db()
        self.assertEqual((vinculo.telegram_id, vinculo.chat_id), (ID_GRANDE, ID_GRANDE + 1))
        self.assertEqual(self.usuario.telegram, vinculo)

    def test_mesma_pessoa_nao_vincula_a_dois_usuarios(self):
        VinculoTelegram.objects.create(usuario=self.usuario, telegram_id=1, chat_id=1)
        outro = User.objects.create_user("bia", password="x")

        with self.assertRaises(IntegrityError), transaction.atomic():
            VinculoTelegram.objects.create(usuario=outro, telegram_id=1, chat_id=2)

    def test_apagar_o_usuario_apaga_o_vinculo(self):
        VinculoTelegram.objects.create(usuario=self.usuario, telegram_id=1, chat_id=1)

        self.usuario.delete()

        self.assertFalse(VinculoTelegram.objects.exists())


class MensagemTelegramTestCase(TestCase):

    def criar(self, **campos):
        return MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.ENTRADA, situacao=MensagemTelegram.Situacao.RECEBIDA, **campos,
        )

    def test_mesmo_update_nao_entra_duas_vezes(self):
        self.criar(update_id=ID_GRANDE)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar(update_id=ID_GRANDE)

    def test_sem_update_id_pode_repetir(self):
        self.criar(update_id=None)
        self.criar(update_id=None)

        self.assertEqual(MensagemTelegram.objects.count(), 2)

    def test_apagar_o_usuario_mantem_a_mensagem(self):
        usuario = User.objects.create_user("ana", password="x")
        mensagem = self.criar(usuario=usuario)

        usuario.delete()

        mensagem.refresh_from_db()
        self.assertIsNone(mensagem.usuario)


class ConfiguracaoTelegramTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        self.addCleanup(cache.delete, ConfiguracaoTelegram.CHAVE_CACHE)

    def test_obter_cria_linha_unica_com_os_padroes(self):
        config = ConfiguracaoTelegram.obter()

        self.assertEqual(config.pk, 1)
        self.assertEqual(
            (config.mensagens_por_minuto, config.arquivos_por_minuto, config.bloqueio_minutos,
             config.desconhecido_mensagens_por_minuto, config.desconhecido_bloqueio_minutos,
             config.desconhecido_aviso_horas, config.reter_conteudo_dias, config.reter_mensagens_dias),
            (20, 4, 5, 5, 60, 12, 30, 60),
        )

        # Mesmo sem cache, não cria uma segunda linha
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        ConfiguracaoTelegram.obter()
        self.assertEqual(ConfiguracaoTelegram.objects.count(), 1)

    def test_obter_usa_o_cache(self):
        ConfiguracaoTelegram.obter()

        with self.assertNumQueries(0):
            ConfiguracaoTelegram.obter()

    def test_salvar_vale_na_hora_e_mantem_a_linha_unica(self):
        ConfiguracaoTelegram.obter()

        ConfiguracaoTelegram(mensagens_por_minuto=7).save()

        self.assertEqual(ConfiguracaoTelegram.objects.count(), 1)
        self.assertEqual(ConfiguracaoTelegram.obter().mensagens_por_minuto, 7)


class LimiteTelegramTestCase(TestCase):

    def test_comeca_zerado(self):
        limite = LimiteTelegram.objects.create(telegram_id=ID_GRANDE)

        limite.refresh_from_db()
        self.assertEqual((limite.mensagens, limite.arquivos, limite.total, limite.descartadas), (0, 0, 0, 0))
        self.assertFalse(limite.avisou_arquivos)
        self.assertIsNone(limite.bloqueado_ate)


class EsperaTelegramTestCase(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user("ana", password="x")
        self.vinculo = VinculoTelegram.objects.create(usuario=self.usuario, telegram_id=1, chat_id=1)

    def test_referencia_aponta_para_qualquer_registro(self):
        espera = EsperaTelegram.objects.create(vinculo=self.vinculo, campo="data", referencia=self.usuario)

        espera = EsperaTelegram.objects.get(pk=espera.pk)
        self.assertEqual(espera.referencia, self.usuario)
        self.assertEqual(self.vinculo.espera, espera)

    def test_uma_espera_por_pessoa(self):
        EsperaTelegram.objects.create(vinculo=self.vinculo, campo="data")

        with self.assertRaises(IntegrityError), transaction.atomic():
            EsperaTelegram.objects.create(vinculo=self.vinculo, campo="valor")

    def test_trocar_de_pergunta_reinicia_o_prazo(self):
        espera = EsperaTelegram.objects.create(vinculo=self.vinculo, campo="data", desde=timezone.now() - timedelta(hours=1))
        antes = espera.desde

        EsperaTelegram.objects.update_or_create(
            vinculo=self.vinculo, defaults={"campo": "valor", "desde": timezone.now()},
        )

        espera.refresh_from_db()
        self.assertGreater(espera.desde, antes)


class AdminTestCase(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_superuser("root", password="x"))
        # Os 403 aqui são esperados: sem isso, cada um escreve um traceback na saída dos testes
        logger = logging.getLogger("django.request")
        self.addCleanup(logger.setLevel, logger.level)
        logger.setLevel(logging.ERROR)

    def url(self, modelo, acao="changelist"):
        return reverse("admin:telegram_{}_{}".format(modelo, acao))

    def test_mensagem_e_limite_sao_somente_leitura(self):
        mensagem = MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.SAIDA, situacao=MensagemTelegram.Situacao.ENVIADA, texto="oi",
        )
        limite = LimiteTelegram.objects.create(telegram_id=1)

        for modelo, registro in (("mensagemtelegram", mensagem), ("limitetelegram", limite)):
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(self.url(modelo)).status_code, 200)
                self.assertEqual(self.client.get(self.url(modelo, "add")).status_code, 403)
                excluir = reverse("admin:telegram_{}_delete".format(modelo), args=[registro.pk])
                self.assertEqual(self.client.post(excluir, {"post": "yes"}).status_code, 403)
                alterar = reverse("admin:telegram_{}_change".format(modelo), args=[registro.pk])
                self.assertEqual(self.client.get(alterar).status_code, 200)  # abre só para leitura
                self.assertNotContains(self.client.get(alterar), 'name="_save"')

        self.assertTrue(MensagemTelegram.objects.exists())

    def test_busca_de_vinculo(self):
        ana = User.objects.create_user("ana", password="x")
        bia = User.objects.create_user("bia", password="x")
        VinculoTelegram.objects.create(usuario=ana, telegram_id=ID_GRANDE, chat_id=1, username="ana_tg")
        VinculoTelegram.objects.create(usuario=bia, telegram_id=2, chat_id=2, username="bia_tg")

        for termo in ("ana_tg", str(ID_GRANDE)):
            with self.subTest(termo=termo):
                resposta = self.client.get(self.url("vinculotelegram"), {"q": termo})
                self.assertContains(resposta, "ana_tg")
                self.assertNotContains(resposta, "bia_tg")

    def test_configuracao_nao_permite_segunda_linha(self):
        self.assertEqual(self.client.get(self.url("configuracaotelegram", "add")).status_code, 200)

        ConfiguracaoTelegram.objects.create(pk=1)

        self.assertEqual(self.client.get(self.url("configuracaotelegram", "add")).status_code, 403)
