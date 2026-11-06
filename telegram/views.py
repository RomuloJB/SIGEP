import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import OuterRef, Subquery
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, TemplateView, UpdateView

from cadastros.views import PaginatedFilterView
from usuarios.views import BaseLoginMixin, SuperuserRequiredMixin

from . import limites, recebimento, services
from .filters import MensagemTelegramFilter, RemetenteTelegramFilter
from .forms import ConfiguracaoTelegramForm
from .models import CodigoVinculoTelegram, ConfiguracaoTelegram, LimiteTelegram, MensagemTelegram, VinculoTelegram

CHAVE_SESSAO_CODIGO = "telegram_codigo"
CABECALHO_SEGREDO = "X-Telegram-Bot-Api-Secret-Token"


# ─── Tela "Telegram" (qualquer usuário logado, só o próprio vínculo) ──────────

class ConexaoTelegramView(BaseLoginMixin, TemplateView):
    template_name = "telegram/conexao.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vinculo"] = VinculoTelegram.objects.filter(usuario=self.request.user).first()
        context["link_do_bot"] = None if context["vinculo"] else self.link_do_bot()
        context["validade_minutos"] = settings.TELEGRAM_CODIGO_VALIDADE_MIN
        return context

    def link_do_bot(self):
        """Link do código guardado na sessão. Código vencido ou já usado sai da sessão."""
        token = self.request.session.get(CHAVE_SESSAO_CODIGO)
        if CodigoVinculoTelegram.buscar_valido(token) is None:
            self.request.session.pop(CHAVE_SESSAO_CODIGO, None)
            return None
        return "https://t.me/{}?start={}".format(settings.TELEGRAM_BOT_USERNAME, token)


class ConectarTelegramView(BaseLoginMixin, View):
    """Botão "Conectar Telegram": gera o código e volta para a tela, que mostra o link."""

    def post(self, request):
        if not VinculoTelegram.objects.filter(usuario=request.user).exists():
            request.session[CHAVE_SESSAO_CODIGO] = CodigoVinculoTelegram.emitir(request.user)
        return redirect("telegram:conexao")


class DesconectarTelegramView(BaseLoginMixin, View):

    def post(self, request):
        if services.desconectar(request.user):
            messages.success(request, "Telegram desconectado.")
        return redirect("telegram:conexao")


# ─── Log do Telegram (só superusuário) ────────────────────────────────────────

class MensagemTelegramList(SuperuserRequiredMixin, BaseLoginMixin, PaginatedFilterView):
    model = MensagemTelegram
    template_name = "telegram/mensagemtelegram_list.html"
    ordering = ["-criado_em"]
    filterset_class = MensagemTelegramFilter

    def get_queryset(self):
        return super().get_queryset().select_related("usuario").defer("conteudo")


class MensagemTelegramDetail(SuperuserRequiredMixin, BaseLoginMixin, DetailView):
    model = MensagemTelegram
    template_name = "telegram/mensagemtelegram_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("usuario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.conteudo is not None:
            context["conteudo_json"] = json.dumps(self.object.conteudo, indent=2, ensure_ascii=False)
        return context


# ─── Remetentes (só superusuário) ─────────────────────────────────────────────

class RemetenteTelegramList(SuperuserRequiredMixin, BaseLoginMixin, PaginatedFilterView):
    model = LimiteTelegram
    template_name = "telegram/limitetelegram_list.html"
    ordering = ["-ultima_vez"]
    filterset_class = RemetenteTelegramFilter

    def get_queryset(self):
        vinculo = VinculoTelegram.objects.filter(telegram_id=OuterRef("telegram_id"))
        return super().get_queryset().annotate(
            usuario_site=Subquery(vinculo.values("usuario__username")[:1]),
            nome_telegram=Subquery(vinculo.values("nome")[:1]),
        )


class RemetenteTelegramLiberar(SuperuserRequiredMixin, BaseLoginMixin, View):
    """Botão "Liberar": encerra o bloqueio do remetente antes do prazo."""

    def post(self, request, pk):
        limites.liberar(get_object_or_404(LimiteTelegram, pk=pk))
        messages.success(request, "Remetente liberado.")
        return redirect("telegram:remetente-list")


# ─── Configuração do Telegram (só superusuário) ───────────────────────────────

class ConfiguracaoTelegramUpdate(SuperuserRequiredMixin, BaseLoginMixin, SuccessMessageMixin, UpdateView):
    model = ConfiguracaoTelegram
    form_class = ConfiguracaoTelegramForm
    template_name = "telegram/configuracaotelegram_form.html"
    success_url = reverse_lazy("telegram:configuracao")
    success_message = "Configuração do Telegram salva."
    extra_context = {"title": "Configuração do Telegram"}

    def get_object(self, queryset=None):
        # Lê do banco (e não do cache de 30 s) para editar sempre a versão atual
        config, _ = ConfiguracaoTelegram.objects.get_or_create(pk=1)
        return config


# ─── Webhook (rota chamada pelo Telegram) ─────────────────────────────────────

@csrf_exempt
@require_POST
@sensitive_variables("esperado", "recebido")
def webhook(request):
    """Recebe os updates do bot. Autenticado pelo cabeçalho que o Telegram envia, comparado com o .env."""
    esperado = settings.TELEGRAM_WEBHOOK_SECRET
    if not esperado:
        return HttpResponse("Webhook não configurado.", status=503)
    recebido = request.headers.get(CABECALHO_SEGREDO, "")
    if not hmac.compare_digest(recebido.encode(), esperado.encode()):
        return HttpResponseForbidden("Segredo inválido.")
    try:
        update = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("JSON inválido.")
    # Sem update_id, o get_or_create do log acharia as saídas, que têm esse campo vazio
    if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
        return HttpResponseBadRequest("JSON inválido.")
    recebimento.receber(update)
    return HttpResponse()
