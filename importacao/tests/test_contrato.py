import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from importacao.importadores import (
    REGISTRO, REGRA_DE_SEGURANCA, SEM_ITENS, Campo, obter_importador, registrar, tipos_disponiveis,
)

from .base import ImportadorTeste, OutroImportador


class CampoTestCase(SimpleTestCase):

    def test_codigo_de_ate_6_caracteres(self):
        Campo("valor", "Valor", "valor")
        with self.assertRaises(ValueError):
            Campo("1234567", "Valor", "valor")
        with self.assertRaises(ValueError):
            Campo("", "Valor", "valor")

    def test_tipo_desconhecido(self):
        with self.assertRaises(ValueError):
            Campo("x", "X", "numero")

    def test_escolha_precisa_de_opcoes(self):
        with self.assertRaises(ValueError):
            Campo("cat", "Categoria", "escolha")
        Campo("cat", "Categoria", "escolha", opcoes=lambda usuario, escopo: [(1, "Mercado")])


class RegistroTestCase(SimpleTestCase):

    def setUp(self):
        registro = mock.patch.dict(REGISTRO, {}, clear=True)
        registro.start()
        self.addCleanup(registro.stop)

    def test_registrar_e_obter(self):
        registrar(ImportadorTeste)
        registrar(OutroImportador)

        self.assertIsInstance(obter_importador("teste.grupo"), ImportadorTeste)
        self.assertIsNone(obter_importador("nao.existe"))
        self.assertEqual(tipos_disponiveis(), [("teste.grupo", "Grupo de teste"), ("teste.outro", "Outro documento")])

    def test_registrar_de_novo_a_mesma_classe_nao_quebra(self):
        registrar(ImportadorTeste)
        registrar(ImportadorTeste)
        self.assertEqual(len(REGISTRO), 1)

    def test_dois_importadores_com_o_mesmo_tipo(self):
        registrar(ImportadorTeste)

        class Copia(ImportadorTeste):
            pass

        with self.assertRaises(ImproperlyConfigured):
            registrar(Copia)

    def test_instrucoes_sem_a_regra_de_seguranca_sao_recusadas(self):
        class SemRegra(ImportadorTeste):
            tipo = "teste.sem_regra"
            instrucoes = "Leia a nota."

        with self.assertRaisesMessage(ImproperlyConfigured, "REGRA_DE_SEGURANCA"):
            registrar(SemRegra)

    def test_contrato_incompleto_e_recusado(self):
        class SemVersao(ImportadorTeste):
            tipo = "teste.sem_versao"
            versao_prompt = ""

        with self.assertRaisesMessage(ImproperlyConfigured, "versao_prompt"):
            registrar(SemVersao)

    def test_instrucoes_sem_itens_mantem_a_regra_no_fim(self):
        instrucoes = ImportadorTeste().instrucoes_sem_itens()

        self.assertIn(SEM_ITENS, instrucoes)
        self.assertTrue(instrucoes.endswith(REGRA_DE_SEGURANCA))
        self.assertEqual(instrucoes.count(REGRA_DE_SEGURANCA), 1)


class IsolamentoTestCase(SimpleTestCase):
    """A seta mais importante é a que não existe: o importacao nunca importa um app de domínio."""

    def test_importacao_nao_importa_apps_do_projeto(self):
        pasta = Path(settings.BASE_DIR) / "importacao"
        proibido = re.compile(r"^\s*(from|import)\s+(cadastros|telegram|usuarios|website|sigep|license)\b", re.M)
        culpados = [
            str(arquivo.relative_to(pasta)) for arquivo in pasta.rglob("*.py")
            if "tests" not in arquivo.parts and proibido.search(arquivo.read_text(encoding="utf-8"))
        ]
        self.assertEqual(culpados, [])

    def test_importacao_nao_fala_direto_com_o_gemini(self):
        pasta = Path(settings.BASE_DIR) / "importacao"
        for arquivo in pasta.rglob("*.py"):
            if "tests" in arquivo.parts:
                continue
            self.assertNotIn("google.genai", arquivo.read_text(encoding="utf-8"), str(arquivo))
