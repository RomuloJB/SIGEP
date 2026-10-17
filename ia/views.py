import hmac
import os
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.generic import DeleteView, DetailView, TemplateView, UpdateView

from cadastros.views import ExclusaoProtegidaMixin, PaginatedFilterView
from usuarios.views import BaseLoginMixin, SuperuserRequiredMixin

from . import cota
from .chamada import testar_conexao
from .filters import RequisicaoIAFilter, UsuarioIAFilter
from .forms import ConfiguracaoIAForm, ConfiguracaoIAUsuarioForm
from .manutencao import limpar_requisicoes
from .models import ConfiguracaoIA, ConfiguracaoIAUsuario, ConsumoIA, RequisicaoIA
from .provedores.base import ErroIA


def inicio_do_mes(mes):
    """Primeiro instante do mês no fuso da cota (America/Sao_Paulo)."""
    return datetime.combine(mes, time.min, tzinfo=cota.FUSO)


# ─── Requisições de IA (só superusuário) ──────────────────────────────────────

class RequisicaoIAList(SuperuserRequiredMixin, BaseLoginMixin, PaginatedFilterView):
    model = RequisicaoIA
    template_name = "ia/requisicaoia_list.html"
    ordering = ["-criado_em"]
    filterset_class = RequisicaoIAFilter

    def get_queryset(self):
        return super().get_queryset().select_related("usuario", "referencia_tipo").prefetch_related("referencia")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resumo"] = self.resumo_do_mes()
        return context

    def resumo_do_mes(self):
        mes = cota.mes_atual()
        consumo = ConsumoIA.objects.filter(mes=mes)
        totais = consumo.aggregate(tokens=Sum("tokens_total"), custo=Sum("custo_estimado"))
        requisicoes = RequisicaoIA.objects.filter(criado_em__gte=inicio_do_mes(mes))

        maiores_referencias = []
        for linha in (
            requisicoes.filter(referencia_tipo__isnull=False, referencia_id__isnull=False)
            .values("referencia_tipo", "referencia_id")
            .annotate(tokens=Sum("tokens_total"))
            .order_by("-tokens")[:5]
        ):
            tipo = ContentType.objects.get_for_id(linha["referencia_tipo"])
            try:
                nome = str(tipo.get_object_for_this_type(pk=linha["referencia_id"]))
            except Exception:
                nome = "{} #{} (excluído)".format(tipo.name, linha["referencia_id"])
            maiores_referencias.append({"nome": nome, "tokens": linha["tokens"]})

        return {
            "mes": mes,
            "tokens": totais["tokens"] or 0,
            "custo": totais["custo"] or 0,
            "erros": requisicoes.exclude(situacao=RequisicaoIA.Situacao.SUCESSO).count(),
            "maiores_referencias": maiores_referencias,
            "maiores_usuarios": consumo.select_related("usuario").order_by("-tokens_total")[:5],
        }


class RequisicaoIADetail(SuperuserRequiredMixin, BaseLoginMixin, DetailView):
    model = RequisicaoIA
    template_name = "ia/requisicaoia_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("usuario", "referencia_tipo")


# ─── Meu consumo (qualquer usuário logado) ────────────────────────────────────

class MeuConsumoView(BaseLoginMixin, TemplateView):
    template_name = "ia/meu_consumo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        situacao = cota.situacao_da_cota(cota.dono_da_cota(usuario))
        context["situacao"] = situacao
        context["largura_barra"] = min(situacao.percentual, 100)
        context["ia_desligada"] = ConfiguracaoIAUsuario.objects.filter(usuario=usuario, ia_habilitada=False).exists()
        context["ultimas_requisicoes"] = RequisicaoIA.objects.filter(usuario=usuario).order_by("-criado_em")[:20]
        return context


# ─── Configuração da IA (só superusuário) ─────────────────────────────────────

class ConfiguracaoIAUpdate(SuperuserRequiredMixin, BaseLoginMixin, SuccessMessageMixin, UpdateView):
    model = ConfiguracaoIA
    form_class = ConfiguracaoIAForm
    template_name = "ia/configuracaoia_form.html"
    success_url = reverse_lazy("ia:configuracao")
    success_message = "Configuração da IA salva. Ela vale a partir da próxima chamada."
    extra_context = {"title": "Configuração da IA"}

    def get_object(self, queryset=None):
        # Lê do banco (e não do cache de 30 s) para editar sempre a versão atual
        config, _ = ConfiguracaoIA.objects.get_or_create(pk=1)
        return config


class TestarConexaoView(SuperuserRequiredMixin, BaseLoginMixin, View):
    """Botão "Testar conexão": faz um pedido mínimo com a configuração salva."""

    def post(self, request):
        try:
            resposta = testar_conexao(request.user)
        except ErroIA as erro:
            messages.error(request, "Falha no teste de conexão ({}): {}".format(erro.situacao, erro))
        else:
            messages.success(
                request,
                "Conexão funcionando: o modelo {} respondeu usando {} tokens.".format(resposta.modelo, resposta.uso.total),
            )
        return redirect("ia:configuracao")


# ─── IA por usuário (só superusuário) ─────────────────────────────────────────

class UsuarioIAList(SuperuserRequiredMixin, BaseLoginMixin, PaginatedFilterView):
    model = User
    template_name = "ia/usuario_ia_list.html"
    ordering = ["username"]
    filterset_class = UsuarioIAFilter

    def get_queryset(self):
        uso_do_mes = ConsumoIA.objects.filter(usuario=OuterRef("pk"), mes=cota.mes_atual()).values("tokens_total")
        return super().get_queryset().annotate(
            excecao_id=F("configuracao_ia__id"),
            limite_proprio=F("configuracao_ia__limite_mensal"),
            ia_habilitada=Coalesce(F("configuracao_ia__ia_habilitada"), Value(True)),
            uso_mes=Coalesce(Subquery(uso_do_mes[:1]), Value(0)),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["limite_padrao"] = ConfiguracaoIA.obter().limite_mensal_usuario
        return context


class UsuarioIAMixin:
    """Busca o usuário da URL (usuario_id) para as telas de exceção de IA."""

    def get_usuario(self):
        if not hasattr(self, "_usuario"):
            self._usuario = get_object_or_404(User, pk=self.kwargs["usuario_id"])
        return self._usuario


class ConfiguracaoIAUsuarioUpdate(SuperuserRequiredMixin, BaseLoginMixin, UsuarioIAMixin, SuccessMessageMixin, UpdateView):
    model = ConfiguracaoIAUsuario
    form_class = ConfiguracaoIAUsuarioForm
    template_name = "ia/configuracaoiausuario_form.html"
    success_url = reverse_lazy("ia:usuario-list")

    def get_object(self, queryset=None):
        # Sem exceção cadastrada, o formulário começa com os padrões e cria a linha ao salvar
        usuario = self.get_usuario()
        try:
            return usuario.configuracao_ia
        except ConfiguracaoIAUsuario.DoesNotExist:
            return ConfiguracaoIAUsuario(usuario=usuario)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["limite_padrao"] = ConfiguracaoIA.obter().limite_mensal_usuario
        return kwargs

    def get_success_message(self, cleaned_data):
        return "Configuração de IA de {} salva.".format(self.get_usuario())


class ConfiguracaoIAUsuarioPadrao(ExclusaoProtegidaMixin, SuperuserRequiredMixin, BaseLoginMixin, UsuarioIAMixin,
                                  SuccessMessageMixin, DeleteView):
    """"Voltar ao padrão": apaga a exceção; o usuário volta aos limites da configuração."""
    model = ConfiguracaoIAUsuario
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("ia:usuario-list")
    extra_context = {"title": "Voltar ao padrão"}

    def get_object(self, queryset=None):
        return get_object_or_404(ConfiguracaoIAUsuario, usuario=self.get_usuario())

    def get_success_message(self, cleaned_data):
        return "A IA de {} voltou ao padrão.".format(self.get_usuario())
