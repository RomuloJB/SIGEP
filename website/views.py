from django.views.generic import TemplateView
from django.db.models import Sum
from django.utils import timezone
from cadastros.models import Order, Client

class IndexView(TemplateView):
    template_name = "website/model.html"

 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Total em vendas
        total_vendas = Order.objects.aggregate(total=Sum('total_value'))['total'] or 0
        
        # 2. Vendas neste mês
        hoje = timezone.now()
        vendas_mes = Order.objects.filter(
            created_at__year=hoje.year,
            created_at__month=hoje.month
        ).aggregate(total=Sum('total_value'))['total'] or 0
        
        # 3. Quantidade de vendas (total de pedidos)
        qtd_vendas = Order.objects.count()
        
        # 4. Quantidade de clientes
        qtd_clientes = Client.objects.count()

        # Extra: Pega os últimos 10 pedidos para preencher aquela tabela do final
        ultimos_pedidos = Order.objects.select_related('client').order_by('-created_at')[:10]
        
        context['total_vendas'] = total_vendas
        context['vendas_mes'] = vendas_mes
        context['qtd_vendas'] = qtd_vendas
        context['qtd_clientes'] = qtd_clientes
        context['ultimos_pedidos'] = ultimos_pedidos
        
        return context

class ContactView(TemplateView):
    template_name = "website/contact.html"

class AboutView(TemplateView):
    template_name = "website/startbootstrap-sigep/about.html"

# erros

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/401.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/404.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/500.html"