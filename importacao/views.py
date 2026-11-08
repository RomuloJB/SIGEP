import hmac
import json
import logging
import os

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.generic import DetailView, FormView, UpdateView
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView

from . import services, tarefas
from .filters import ImportacaoFilter
from .forms import ArquivoForm, ConfiguracaoImportacaoForm, NovaImportacaoForm, TipoForm
from .importadores import REGISTRO, ImportacaoInvalida
from .models import ConfiguracaoImportacao, Importacao

logger = logging.getLogger(__name__)
S = Importacao.Situacao
CANAL = Importacao.Origem.SITE


# O app importacao não importa apps de domínio (cadastros, usuarios...): por isso os mixins de
# acesso vêm do Django e a listagem repete aqui as poucas linhas da PaginatedFilterView.

class BaseLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy("login")


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class PaginatedFilterView(FilterView):
    """Igual à de cadastros/views.py: 10 por página e o número de filtros ativos para o botão."""
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.filterset.form
        if form.is_valid():
            context["active_filters"] = sum(1 for valor in form.cleaned_data.values() if valor not in (None, "", []))
        return context


class ImportacaoDoUsuarioMixin(BaseLoginMixin):
    """Cada pessoa só vê as próprias importações: a de outra pessoa dá 404."""

    def get_queryset(self):
        return super().get_queryset().filter(criado_por=self.request.user)


def _guardar_e_ler(importacao, arquivo):
    services.guardar_arquivo(importacao, arquivo.read(), arquivo.content_type)
    if importacao.situacao == S.PROCESSANDO:
        services.agendar_leitura(importacao)


# ─── Telas da pessoa ──────────────────────────────────────────────────────────

class ImportacaoList(ImportacaoDoUsuarioMixin, PaginatedFilterView):
    model = Importacao
    template_name = "importacao/importacao_list.html"
    ordering = ["-criado_em"]
    filterset_class = ImportacaoFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tem_tipos"] = bool(REGISTRO)
        return context


class NovaImportacaoView(BaseLoginMixin, FormView):
    template_name = "importacao/importacao_form.html"
    form_class = NovaImportacaoForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tem_tipos"] = bool(REGISTRO)
        return context

    def form_valid(self, form):
        arquivo = form.cleaned_data["arquivo"]
        try:
            importacao = services.iniciar_importacao(
                self.request.user, CANAL, tipo=form.cleaned_data.get("tipo", ""),
                observacao=form.cleaned_data["observacao"], arquivo_nome=arquivo.name,
                arquivo_mime=arquivo.content_type, arquivo_tamanho=arquivo.size,
            )
        except services.ImportacaoRecusada as erro:
            form.add_error(None, str(erro))
            return self.form_invalid(form)
        _guardar_e_ler(importacao, arquivo)
        return redirect("importacao:detalhe", importacao.pk)


class ImportacaoDetail(ImportacaoDoUsuarioMixin, DetailView):
    model = Importacao
    template_name = "importacao/importacao_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        importador = self.object.importador
        if importador and self.object.dados:
            context["resumo"] = importador.resumo(self.object.dados)
        if self.object.situacao == S.AGUARDANDO_TIPO:
            context["tipo_form"] = TipoForm()
        if self.object.pode_tentar_de_novo:
            context["arquivo_form"] = ArquivoForm()
        objeto = self.object.objeto if self.object.situacao == S.CONFIRMADA else None
        if objeto is not None and hasattr(objeto, "get_absolute_url"):
            context["url_do_registro"] = objeto.get_absolute_url()
        return context


class ImportacaoRevisar(ImportacaoDoUsuarioMixin, DetailView):
    """O form do app preenchido com o rascunho. Confirmar cria o registro pelo importador."""
    model = Importacao
    template_name = "importacao/importacao_revisar.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.object = self.get_object()
        self.importador = self.object.importador
        if self.object.situacao != S.PRONTA or self.importador is None:
            messages.info(request, services.MSG_NAO_PRONTA)
            return redirect("importacao:detalhe", self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = self.importador.form(request.user, initial=self.importador.dados_para_form(self.object.dados))
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        dados_form = request.POST if self.importador.form_class else None
        try:
            services.confirmar_importacao(self.object, request.user, CANAL, dados_form=dados_form)
        except ImportacaoInvalida as erro:
            form = erro.form or self.importador.form(request.user, data=request.POST)
            if form is None or not form.errors:
                messages.error(request, "O registro não pôde ser criado: {}".format(erro.erros))
            return self.render_to_response(self.get_context_data(form=form))
        except services.AcaoInvalida as erro:
            messages.warning(request, str(erro))
            return redirect("importacao:detalhe", self.object.pk)
        messages.success(request, "Importação confirmada: o registro foi criado.")
        return redirect("importacao:detalhe", self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resumo"] = self.importador.resumo(self.object.dados)
        return context


class AcaoImportacaoView(ImportacaoDoUsuarioMixin, SingleObjectMixin, View):
    """Base dos botões da tela de detalhe: POST e volta para o detalhe."""
    model = Importacao
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.executar(request)
        except (services.AcaoInvalida, services.ImportacaoRecusada) as erro:
            messages.warning(request, str(erro))
        return redirect("importacao:detalhe", self.object.pk)


class ImportacaoDescartar(AcaoImportacaoView):

    def executar(self, request):
        services.descartar_importacao(self.object, request.user, CANAL)
        messages.success(request, "Importação descartada.")


class ImportacaoEscolherTipo(AcaoImportacaoView):

    def executar(self, request):
        form = TipoForm(request.POST)
        if not form.is_valid():
            raise services.AcaoInvalida("Escolha o tipo do documento.")
        services.agendar_leitura(services.escolher_tipo(self.object, form.cleaned_data["tipo"], request.user, CANAL))


class ImportacaoTentarDeNovo(AcaoImportacaoView):
    """No site, ler de novo pede o arquivo outra vez: ele não fica guardado."""

    def executar(self, request):
        form = ArquivoForm(request.POST, request.FILES)
        if not form.is_valid():
            raise services.AcaoInvalida(" ".join(form.errors.get("arquivo", ["Envie o arquivo de novo."])))
        importacao = services.preparar_nova_tentativa(self.object, request.user, CANAL)
        _guardar_e_ler(importacao, form.cleaned_data["arquivo"])


# ─── Configuração (só superusuário) ───────────────────────────────────────────

class ConfiguracaoImportacaoUpdate(SuperuserRequiredMixin, BaseLoginMixin, SuccessMessageMixin, UpdateView):
    model = ConfiguracaoImportacao
    form_class = ConfiguracaoImportacaoForm
    template_name = "importacao/configuracaoimportacao_form.html"
    success_url = reverse_lazy("importacao:configuracao")
    success_message = "Configuração da importação salva."

    def get_object(self, queryset=None):
        # Lê do banco (e não do cache de 30 s) para editar sempre a versão atual
        config, _ = ConfiguracaoImportacao.objects.get_or_create(pk=1)
        return config


# ─── Tarefas (rota chamada pelo Cloud Tasks) ──────────────────────────────────

@sensitive_variables("esperado", "recebido")
def _tarefa_autorizada(request):
    esperado = os.getenv("TAREFAS_SEGREDO", "")
    recebido = request.headers.get(tarefas.CABECALHO_SEGREDO, "")
    return bool(esperado) and hmac.compare_digest(recebido.encode(), esperado.encode())


@method_decorator(csrf_exempt, name="dispatch")
class TarefaView(View):
    """POST do Cloud Tasks: roda a tarefa com os parâmetros do corpo (JSON)."""
    http_method_names = ["post"]

    def post(self, request, nome):
        if not _tarefa_autorizada(request):
            return HttpResponseForbidden("Segredo inválido.")
        if nome not in tarefas.TAREFAS:
            raise Http404("Tarefa desconhecida.")
        try:
            params = json.loads(request.body or b"{}")
        except ValueError:
            return HttpResponseBadRequest("JSON inválido.")
        if not isinstance(params, dict):
            return HttpResponseBadRequest("JSON inválido.")
        try:
            tarefas.executar(nome, params)
        except Exception:
            # Repetir não ajuda: a leitura trava a importação e a manutenção destrava as presas
            logger.exception("Falha na tarefa %s.", nome)
        return HttpResponse()
