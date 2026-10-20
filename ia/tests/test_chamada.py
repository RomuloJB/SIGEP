from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase

from cadastros.models import Company
from ia import cota, provedores
from ia.chamada import chamar_ia
from ia.models import ConfiguracaoIA, ConfiguracaoIAUsuario, ConsumoIA, RequisicaoIA
from ia.provedores import obter_provedor
from ia.provedores.base import (
    ErroConfiguracao, ErroTemporario, IaIndisponivel, PedidoIA, UsoTokens,
)


def montar_pedido(config):
    return PedidoIA(instrucoes="Seja breve.", texto="Olá")


class ChamarIATestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        provedores._cache.clear()
        self.configurar(provedor=ConfiguracaoIA.Provedor.FALSO)
        self.usuario = User.objects.create_user("ana", password="x")
        self.empresa = Company.objects.create(name="Empresa", cnpj="00000000000191", created_by=self.usuario)
        # Sem pausa real entre as tentativas
        sono = mock.patch("ia.chamada.time.sleep")
        self.sono = sono.start()
        self.addCleanup(sono.stop)

    def configurar(self, **campos):
        config = ConfiguracaoIA.obter()
        for nome, valor in campos.items():
            setattr(config, nome, valor)
        config.save()

    def provedor(self):
        """O mesmo ProvedorFalso que chamar_ia vai usar com a configuração atual."""
        return obter_provedor(ConfiguracaoIA.obter())

    def chamar(self, usuario=None, **kwargs):
        kwargs.setdefault("finalidade", "teste_responder")
        kwargs.setdefault("montar_pedido", montar_pedido)
        return chamar_ia(usuario=usuario or self.usuario, **kwargs)

    def consumo_do_mes(self, usuario=None):
        return ConsumoIA.objects.get(usuario=usuario or self.usuario, mes=cota.mes_atual())

    def test_sucesso_grava_requisicao_com_referencia_e_soma_consumo(self):
        self.configurar(preco_entrada_milhao=Decimal("1"), preco_saida_milhao=Decimal("2"))
        self.provedor().programar(texto="oi", uso=UsoTokens(entrada=10, saida=5, raciocinio=2))

        resposta = self.chamar(referencia=self.empresa, versao_prompt="v1")

        self.assertEqual(resposta.texto, "oi")
        requisicao = RequisicaoIA.objects.get()
        self.assertEqual(requisicao.situacao, RequisicaoIA.Situacao.SUCESSO)
        self.assertEqual(requisicao.referencia, self.empresa)
        self.assertEqual(requisicao.tentativa, 1)
        self.assertEqual(requisicao.tokens_total, 15)
        self.assertEqual(requisicao.tokens_raciocinio, 2)
        self.assertEqual(requisicao.custo_estimado, Decimal("0.00002"))
        self.assertEqual(len(requisicao.contexto_hash), 64)
        consumo = self.consumo_do_mes()
        self.assertEqual((consumo.tokens_entrada, consumo.tokens_saida, consumo.tokens_total), (10, 5, 15))
        self.assertEqual(consumo.requisicoes, 1)
        self.assertEqual(consumo.mes.day, 1)

    def test_erro_temporario_seguido_de_sucesso_grava_duas_tentativas(self):
        provedor = self.provedor()
        provedor.programar(erro=ErroTemporario("instável", uso=UsoTokens(entrada=4)))
        provedor.programar(texto="ok", uso=UsoTokens(entrada=10, saida=5))

        self.chamar()

        requisicoes = RequisicaoIA.objects.order_by("tentativa")
        self.assertEqual(
            [(r.tentativa, r.situacao) for r in requisicoes],
            [(1, "erro_temporario"), (2, "sucesso")],
        )
        self.sono.assert_called_once_with(1)
        # Tokens do erro também contam
        self.assertEqual(self.consumo_do_mes().tokens_total, 19)

    def test_erro_configuracao_nao_repete(self):
        self.configurar(tentativas=3)
        provedor = self.provedor()
        provedor.programar(erro=ErroConfiguracao("modelo inexistente"))
        provedor.programar(texto="não deveria ser usada")

        with self.assertRaises(ErroConfiguracao):
            self.chamar()

        self.assertEqual(len(provedor.pedidos), 1)
        self.assertEqual(RequisicaoIA.objects.get().situacao, "erro_configuracao")
        self.sono.assert_not_called()

    def test_cota_esgotada_nao_chama_provedor(self):
        # Limite padrão 100.000 e reserva 5.000: restam 4.000, abaixo da reserva
        ConsumoIA.objects.create(usuario=self.usuario, mes=cota.mes_atual(), tokens_total=96000)
        provedor = self.provedor()
        montar = mock.Mock(side_effect=montar_pedido)

        with self.assertRaises(cota.CotaExcedida) as contexto:
            self.chamar(montar_pedido=montar)

        self.assertEqual(provedor.pedidos, [])
        montar.assert_not_called()
        requisicao = RequisicaoIA.objects.get()
        self.assertEqual((requisicao.situacao, requisicao.tentativa), ("bloqueada_cota", 0))
        renova = cota.proximo_mes(cota.mes_atual())
        self.assertEqual(str(contexto.exception), "Sua cota de IA acabou. Ela renova em {:%d/%m}.".format(renova))

    def test_limite_proprio_zero_bloqueia_e_vazio_volta_ao_padrao(self):
        excecao = ConfiguracaoIAUsuario.objects.create(usuario=self.usuario, limite_mensal=0)
        with self.assertRaises(cota.CotaExcedida):
            self.chamar()

        excecao.limite_mensal = None
        excecao.save()
        self.assertEqual(cota.limite_do_usuario(self.usuario), ConfiguracaoIA.obter().limite_mensal_usuario)
        self.assertEqual(self.chamar().texto, "ok")

    def test_ia_desligada_para_o_usuario(self):
        ConfiguracaoIAUsuario.objects.create(usuario=self.usuario, ia_habilitada=False)
        with self.assertRaises(IaIndisponivel):
            self.chamar()
        self.assertEqual(RequisicaoIA.objects.get().situacao, "indisponivel")
        self.assertEqual(self.provedor().pedidos, [])

    def test_falha_ao_gravar_auditoria_nao_derruba_chamada(self):
        self.provedor().programar(texto="oi", uso=UsoTokens(entrada=10, saida=5))

        with mock.patch.object(RequisicaoIA.objects, "create", side_effect=DatabaseError("banco fora")):
            with self.assertLogs("ia.chamada", level="ERROR"):
                resposta = self.chamar()

        self.assertEqual(resposta.texto, "oi")
        self.assertFalse(RequisicaoIA.objects.exists())
        self.assertEqual(self.consumo_do_mes().tokens_total, 15)

    def test_teto_do_sistema_bloqueia_todos(self):
        self.configurar(limite_mensal_sistema=1000)
        outro = User.objects.create_user("bia", password="x")
        ConsumoIA.objects.create(usuario=outro, mes=cota.mes_atual(), tokens_total=1000)

        for usuario in (self.usuario, outro):
            with self.assertRaises(IaIndisponivel):
                self.chamar(usuario=usuario)

        self.assertEqual(self.provedor().pedidos, [])
        self.assertEqual(RequisicaoIA.objects.filter(situacao="indisponivel").count(), 2)

    def test_consumo_de_mes_anterior_nao_conta(self):
        mes_passado = date(2026, 9, 1)
        ConsumoIA.objects.create(usuario=self.usuario, mes=mes_passado, tokens_total=500000)

        with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 10, 15, 12, tzinfo=dt_timezone.utc)):
            self.assertEqual(cota.situacao_da_cota(self.usuario).usado, 0)
            self.assertEqual(self.chamar().texto, "ok")

    def test_mes_atual_usa_fuso_de_sao_paulo(self):
        # 01/11 às 02h UTC ainda é 31/10 às 23h em São Paulo
        with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 11, 1, 2, tzinfo=dt_timezone.utc)):
            self.assertEqual(cota.mes_atual(), date(2026, 10, 1))
        self.assertEqual(cota.proximo_mes(date(2026, 12, 1)), date(2027, 1, 1))
