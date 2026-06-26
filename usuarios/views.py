from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from cadastros.models import Company

class BaseLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy('login')


class SelectCompanyView(BaseLoginMixin, ListView):
    """
    Exibe a lista de empresas às quais o usuário logado tem acesso
    (seja como gerente ou como representante de vendas).
    """
    model = Company
    template_name = "usuarios/select_company.html"
    context_object_name = "companies"

    def get_queryset(self):
        return Company.objects.filter(
            Q(manager=self.request.user) | Q(sales_rep=self.request.user)
        ).distinct()


class ActivateCompanyView(BaseLoginMixin, View):
    """
    Ativa a empresa selecionada pelo usuário salvando seu ID e nome na sessão.
    """
    def get(self, request, pk):
        company = get_object_or_404(
            Company,
            Q(manager=request.user) | Q(sales_rep=request.user),
            pk=pk
        )
        request.session['active_company_id'] = company.id
        request.session['company_name'] = company.name
        return redirect('index')


class ActiveCompanyRequiredMixin(BaseLoginMixin):
    """
    Mixin para obrigar o usuário a ter uma empresa ativa selecionada na sessão.
    Filtra automaticamente o queryset para retornar apenas registros da empresa ativa.
    Vincula automaticamente novos registros criados à empresa ativa.
    Filtra os campos ForeignKey dos formulários para exibirem apenas opções da empresa ativa.
    """
    active_company = None

    def dispatch(self, request, *args, **kwargs):
        # Verifica se está autenticado
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_company_id = request.session.get('active_company_id')
        if not active_company_id:
            return redirect('select-company')

        try:
            self.active_company = Company.objects.get(
                Q(manager=request.user) | Q(sales_rep=request.user),
                pk=active_company_id
            )
        except Company.DoesNotExist:
            # Limpa sessão se a empresa não existe ou o usuário perdeu acesso
            if 'active_company_id' in request.session:
                del request.session['active_company_id']
            if 'company_name' in request.session:
                del request.session['company_name']
            return redirect('select-company')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtra registros pelo Tenant (Empresa Ativa)
        from cadastros.models import ProductOrder
        if hasattr(self.model, 'company'):
            queryset = queryset.filter(company=self.active_company)
        elif self.model == Company:
            queryset = queryset.filter(id=self.active_company.id)
        elif self.model == ProductOrder:
            queryset = queryset.filter(order__company=self.active_company)
        return queryset

    def form_valid(self, form):
        # Associa automaticamente o objeto à empresa ativa na criação/atualização
        if hasattr(form.instance, 'company') and not getattr(form.instance, 'company', None):
            form.instance.company = self.active_company
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtra as opções de ForeignKey para que listem apenas registros da empresa ativa
        for field_name, field in form.fields.items():
            if hasattr(field, 'queryset'):
                model = field.queryset.model
                if hasattr(model, 'company'):
                    field.queryset = field.queryset.filter(company=self.active_company)
                elif model == Company:
                    field.queryset = field.queryset.filter(id=self.active_company.id)
        return form
