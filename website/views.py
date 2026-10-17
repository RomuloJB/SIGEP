from datetime import date, datetime, time

from braces.views import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from cadastros.models import Client

from usuarios.views import ActiveCompanyRequiredMixin

MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ultimos_meses(qtd, hoje=None):
    """Lista de (ano, mês) dos últimos `qtd` meses, terminando no mês atual."""
    hoje = hoje or timezone.localdate()
    indice = hoje.year * 12 + (hoje.month - 1)
    meses = []
    for i in range(indice - qtd + 1, indice + 1):
        ano, mes0 = divmod(i, 12)
        meses.append((ano, mes0 + 1))
    return meses


class IndexView(ActiveCompanyRequiredMixin, TemplateView):
    template_name = "website/model.html"

    def vendas_por_mes(self, qtd_meses=12):
        """
        Dados dos gráficos do dashboard: valor vendido e quantidade de pedidos por
        mês nos últimos `qtd_meses` (meses sem pedido entram com zero), usando o
        mesmo critério dos cards (pedidos visíveis ao usuário na empresa ativa).
        """
        meses = ultimos_meses(qtd_meses)
        inicio = timezone.make_aware(datetime.combine(date(*meses[0], 1), time.min))

        por_mes = {
            (linha["mes"].year, linha["mes"].month): linha
            for linha in (
                self.pedidos_visiveis().filter(created_at__gte=inicio)
                .annotate(mes=TruncMonth("created_at"))
                .values("mes")
                .annotate(total=Sum("total_value"), qtd=Count("id"))
            )
        }

        labels, valores, quantidades = [], [], []
        for ano, mes in meses:
            linha = por_mes.get((ano, mes))
            labels.append(f"{MESES_ABREV[mes - 1]}/{str(ano)[2:]}")
            valores.append(float(linha["total"]) if linha else 0.0)
            quantidades.append(linha["qtd"] if linha else 0)

        return {"labels": labels, "valores": valores, "quantidades": quantidades}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Gerente: pedidos da empresa ativa; representante: só os dele (RN02)
        pedidos = self.pedidos_visiveis()

        # 1. Total em vendas
        total_vendas = pedidos.aggregate(total=Sum('total_value'))['total'] or 0

        # 2. Vendas neste mês
        hoje = timezone.now()
        vendas_mes = pedidos.filter(
            created_at__year=hoje.year,
            created_at__month=hoje.month
        ).aggregate(total=Sum('total_value'))['total'] or 0

        # 3. Quantidade de vendas
        qtd_vendas = pedidos.count()

        # 4. Quantidade de clientes (da empresa ativa)
        qtd_clientes = Client.objects.filter(company=self.active_company).count()

        # Extra: Pega os últimos 10 pedidos
        ultimos_pedidos = pedidos.select_related('client').order_by('-created_at')[:10]
        
        context['total_vendas'] = total_vendas
        context['vendas_mes'] = vendas_mes
        context['qtd_vendas'] = qtd_vendas
        context['qtd_clientes'] = qtd_clientes
        context['ultimos_pedidos'] = ultimos_pedidos
        context['chart_data'] = self.vendas_por_mes()

        return context

class BaseLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy('login')

class ContactView(TemplateView, BaseLoginMixin):
    template_name = "website/contact.html"

class AboutView(TemplateView, BaseLoginMixin):
    template_name = "website/startbootstrap-sigep/about.html"

# erros

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/401.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/404.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/500.html"