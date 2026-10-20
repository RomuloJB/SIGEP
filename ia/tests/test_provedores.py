import os
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from ia import provedores
from ia.models import ConfiguracaoIA
from ia.provedores import obter_provedor
from ia.provedores.base import ErroConfiguracao, PedidoIA, TempoEsgotado, UsoTokens
from ia.provedores.falso import ProvedorFalso


class ProvedoresTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        provedores._cache.clear()

    def test_obter_cria_linha_unica_e_devolve_a_mesma(self):
        primeira = ConfiguracaoIA.obter()
        segunda = ConfiguracaoIA.obter()

        self.assertEqual(primeira.pk, 1)
        self.assertEqual(segunda.pk, 1)
        self.assertEqual(ConfiguracaoIA.objects.count(), 1)

        # Mesmo sem cache, não cria uma segunda linha
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        ConfiguracaoIA.obter()
        self.assertEqual(ConfiguracaoIA.objects.count(), 1)

    def test_salvar_configuracao_cria_cliente_novo(self):
        momentos = [datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc),
                    datetime(2026, 10, 1, 12, 5, tzinfo=dt_timezone.utc)]
        config = ConfiguracaoIA.obter()
        config.provedor = ConfiguracaoIA.Provedor.FALSO

        with mock.patch("django.utils.timezone.now", return_value=momentos[0]):
            config.save()
        primeiro = obter_provedor(ConfiguracaoIA.obter())
        self.assertIs(obter_provedor(ConfiguracaoIA.obter()), primeiro)

        config.temperatura = 1
        with mock.patch("django.utils.timezone.now", return_value=momentos[1]):
            config.save()
        segundo = obter_provedor(ConfiguracaoIA.obter())

        self.assertIsInstance(segundo, ProvedorFalso)
        self.assertIsNot(segundo, primeiro)

    def test_provedor_falso_devolve_respostas_programadas_em_ordem(self):
        provedor = ProvedorFalso()
        provedor.programar(texto="primeira", uso=UsoTokens(entrada=10, saida=5))
        provedor.programar(texto="segunda")
        provedor.programar(erro=TempoEsgotado("demorou"))
        pedido = PedidoIA(instrucoes="Seja breve.", texto="Olá")

        primeira = provedor.gerar(pedido)
        self.assertEqual(primeira.texto, "primeira")
        self.assertEqual(primeira.uso.total, 15)
        self.assertEqual(provedor.gerar(pedido).texto, "segunda")
        with self.assertRaises(TempoEsgotado) as contexto:
            provedor.gerar(pedido)
        self.assertEqual(contexto.exception.situacao, "tempo_esgotado")

        # Fila vazia devolve "ok"
        self.assertEqual(provedor.gerar(pedido).texto, "ok")
        self.assertEqual(len(provedor.pedidos), 4)

    def test_gemini_sem_chave_levanta_erro_configuracao(self):
        config = ConfiguracaoIA.obter()
        self.assertEqual(config.provedor, ConfiguracaoIA.Provedor.GEMINI)

        ambiente = {nome: valor for nome, valor in os.environ.items() if nome != "GEMINI_API_KEY"}
        with mock.patch.dict(os.environ, ambiente, clear=True):
            with self.assertRaises(ErroConfiguracao) as contexto:
                obter_provedor(config)
        self.assertIn("GEMINI_API_KEY", str(contexto.exception))
