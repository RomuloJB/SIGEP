"""
Importador de teste e apoio comum. O importador cria um Group do Django: assim os testes não
dependem de nenhum app de domínio, como o próprio app importacao.
"""
from io import BytesIO
from unittest import mock

import pydantic
from django import forms
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, override_settings
from PIL import Image

from ia import provedores
from ia.models import ConfiguracaoIA
from importacao.importadores import (
    REGISTRO, REGRA_DE_SEGURANCA, AjusteInvalido, Campo, ImportacaoInvalida, Importador, NaoReconhecido,
)
from importacao.models import ConfiguracaoImportacao, Importacao

TIPO = "teste.grupo"


class NotaTeste(pydantic.BaseModel):
    documento_reconhecido: bool
    motivo_nao_reconhecido: str | None = None
    nome: str | None = None
    itens: list[str] = []


class NotaTesteSemItens(pydantic.BaseModel):
    documento_reconhecido: bool
    motivo_nao_reconhecido: str | None = None
    nome: str | None = None


class GrupoForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=150)


class ImportadorTeste(Importador):
    tipo = TIPO
    nome = "Grupo de teste"
    esquema = NotaTeste
    esquema_sem_itens = NotaTesteSemItens
    instrucoes = "Você lê notas de teste.\n\n" + REGRA_DE_SEGURANCA
    versao_prompt = "2026-11.1"
    form_class = GrupoForm

    def contexto(self, usuario, escopo):
        return "Quem envia: {}".format(usuario.username)

    def normalizar(self, extracao, usuario, escopo):
        if not extracao["documento_reconhecido"]:
            raise NaoReconhecido(extracao.get("motivo_nao_reconhecido") or "Não é uma nota.")
        avisos = [] if extracao.get("nome") else ["O nome não foi lido."]
        return {"nome": extracao.get("nome") or "", "itens": extracao.get("itens", [])}, avisos

    def campos(self):
        return [Campo("nome", "Nome", "texto", obrigatorio=True)]

    def resumo(self, dados):
        return [("Nome", dados.get("nome") or "—"), ("Itens", str(len(dados.get("itens", []))))]

    def ajustar(self, dados, codigo, valor, usuario, escopo):
        if codigo != "nome" or not valor.strip():
            raise AjusteInvalido("Digite um nome.")
        dados["nome"] = valor.strip()
        return dados, "Nome alterado."

    def dados_para_form(self, dados):
        return {"nome": dados.get("nome", "")}

    def confirmar(self, dados, usuario, escopo, dados_form=None):
        form = GrupoForm(data=dados_form if dados_form is not None else self.dados_para_form(dados))
        if not form.is_valid():
            raise ImportacaoInvalida(form.errors, form=form)
        return Group.objects.create(name=form.cleaned_data["nome"])


class OutroImportador(ImportadorTeste):
    tipo = "teste.outro"
    nome = "Outro documento"


class ImportadorComEscopo(ImportadorTeste):
    """Exige uma "equipe" no escopo, como o importador de pedidos exige a empresa."""
    tipo = "teste.escopo"
    nome = "Grupo de uma equipe"

    def conferir_escopo(self, usuario, escopo):
        if not escopo.get("equipe"):
            return "Escolha a equipe antes de importar."
        if escopo["equipe"] == "saiu":
            return "Você não está mais nesta equipe."
        return ""

    def contexto(self, usuario, escopo):
        return "Equipe: {}".format(escopo["equipe"])

    def normalizar(self, extracao, usuario, escopo):
        dados, avisos = super().normalizar(extracao, usuario, escopo)
        dados["equipe"] = escopo["equipe"]
        return dados, avisos

    def confirmar(self, dados, usuario, escopo, dados_form=None):
        grupo = super().confirmar(dados, usuario, escopo, dados_form)
        grupo.name = "{} ({})".format(grupo.name, escopo["equipe"])
        grupo.save()
        return grupo


def png(cor="white"):
    saida = BytesIO()
    Image.new("RGB", (20, 20), cor).save(saida, format="PNG")
    return saida.getvalue()


def resposta(**campos):
    """O que a chamar_ia simulada devolve: dados já validados pelo esquema."""
    campos.setdefault("documento_reconhecido", True)
    return mock.Mock(dados=NotaTeste(**campos))


@override_settings(TAREFAS_BACKEND="imediata")
class ImportacaoTestCase(TestCase):
    importadores = (ImportadorTeste,)

    def setUp(self):
        for chave in (ConfiguracaoIA.CHAVE_CACHE, ConfiguracaoImportacao.CHAVE_CACHE):
            cache.delete(chave)
        self.addCleanup(cache.delete, ConfiguracaoImportacao.CHAVE_CACHE)
        provedores._cache.clear()
        registro = mock.patch.dict(REGISTRO, {classe.tipo: classe() for classe in self.importadores}, clear=True)
        registro.start()
        self.addCleanup(registro.stop)
        self.ana = User.objects.create_user("ana", password="x")
        self.bia = User.objects.create_user("bia", password="x")

    def criar(self, usuario=None, situacao=Importacao.Situacao.PROCESSANDO, **campos):
        campos.setdefault("tipo", TIPO)
        return Importacao.objects.create(criado_por=usuario or self.ana, situacao=situacao, **campos)
