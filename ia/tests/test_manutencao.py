import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ia import cota
from ia.manutencao import limpar_requisicoes
from ia.models import ConfiguracaoIA, ConsumoIA, RequisicaoIA

SEGREDO = "segredo-de-teste"


class LimpezaTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        self.usuario = User.objects.create_user("ana", password="x")
        self.config = ConfiguracaoIA.obter()  # reter_requisicoes_dias = 60

    def criar_requisicoes(self, quantidade, dias_atras):
        RequisicaoIA.objects.bulk_create(
            RequisicaoIA(usuario=self.usuario, finalidade="teste_limpeza", provedor="falso", situacao="sucesso")
            for _ in range(quantidade)
        )
        # criado_em é auto_now_add: ajusta depois para simular registros antigos
        recentes = RequisicaoIA.objects.filter(criado_em__gt=timezone.now() - timedelta(minutes=1))
        recentes.update(criado_em=timezone.now() - timedelta(days=dias_atras))

    def test_apaga_so_as_antigas_em_lotes_e_nao_toca_no_consumo(self):
        self.criar_requisicoes(5, dias_atras=61)
        self.criar_requisicoes(3, dias_atras=59)
        ConsumoIA.objects.create(usuario=self.usuario, mes=cota.mes_atual(), tokens_total=500)

        apagadas = limpar_requisicoes(tamanho_lote=2)

        self.assertEqual(apagadas, 5)
        self.assertEqual(RequisicaoIA.objects.count(), 3)
        self.assertEqual(ConsumoIA.objects.get().tokens_total, 500)

    def test_retencao_zero_desliga_a_limpeza(self):
        self.config.reter_requisicoes_dias = 0
        self.config.save()
        self.criar_requisicoes(2, dias_atras=400)

        self.assertEqual(limpar_requisicoes(), 0)
        self.assertEqual(RequisicaoIA.objects.count(), 2)

    def test_comando_ia_limpar(self):
        self.criar_requisicoes(4, dias_atras=90)
        saida = StringIO()

        call_command("ia_limpar", stdout=saida)

        self.assertIn("4 requisições de IA apagadas (mais antigas que 60 dias)", saida.getvalue())
        self.assertFalse(RequisicaoIA.objects.exists())


class RotaManutencaoTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        self.url = reverse("ia:manutencao")
        self.usuario = User.objects.create_user("ana", password="x")
        antiga = RequisicaoIA.objects.create(usuario=self.usuario, finalidade="teste_limpeza", provedor="falso", situacao="sucesso")
        RequisicaoIA.objects.filter(pk=antiga.pk).update(criado_em=timezone.now() - timedelta(days=90))

    def post(self, segredo=None):
        cabecalhos = {"HTTP_X_TAREFAS_SEGREDO": segredo} if segredo is not None else {}
        return self.client.post(self.url, **cabecalhos)

    def test_segredo_correto_roda_a_limpeza(self):
        with mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": SEGREDO}):
            resposta = self.post(SEGREDO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"apagadas": 1})
        self.assertFalse(RequisicaoIA.objects.exists())

    def test_segredo_errado_ou_ausente_recusa(self):
        with mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": SEGREDO}):
            self.assertEqual(self.post("errado").status_code, 403)
            self.assertEqual(self.post().status_code, 403)
        self.assertEqual(RequisicaoIA.objects.count(), 1)

    def test_sem_segredo_configurado_recusa_tudo(self):
        ambiente = {nome: valor for nome, valor in os.environ.items() if nome != "TAREFAS_SEGREDO"}
        with mock.patch.dict(os.environ, ambiente, clear=True):
            self.assertEqual(self.post("").status_code, 403)
        self.assertEqual(RequisicaoIA.objects.count(), 1)

    def test_get_nao_e_aceito(self):
        with mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": SEGREDO}):
            resposta = self.client.get(self.url, HTTP_X_TAREFAS_SEGREDO=SEGREDO)
        self.assertEqual(resposta.status_code, 405)
