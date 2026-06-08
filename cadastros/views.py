from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.urls import reverse_lazy
from django.db.models import Sum

from .models import Company, Client, User_Profile, Order, Product

# Importar o LoginRequiredMixin para proteger as views
from django.contrib.auth.mixins import LoginRequiredMixin

# Adicionar um Mixin para verificar se tem alguma empresa na sessão, caso não tiver, enviar o usuario para a pagina de seleção de empresa

# Define a permissão de um certo grupo para certas ações
from braces.views import GroupRequiredMixin


class IndexView(TemplateView):
    template_name = "cadastros/index.html"

#BaseLogin
class BaseLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy('login')

# Listas Paginadas
class PaginatedListView(ListView):
    paginate_by = 10
    paginate_by_options = (10, 20, 40)

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", self.paginate_by)
        try:
            per_page = int(per_page)
        except (TypeError, ValueError):
            return self.paginate_by

        if per_page in self.paginate_by_options:
            return per_page

        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page_options"] = self.paginate_by_options
        return context


# Company
class CompanyCreate(GroupRequiredMixin, BaseLoginMixin, CreateView):
    group_required = ['Manager']
    model = Company
    fields = ["name", "description", "cnpj", "manager", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Cadastro de Empresa", "botao": "Criar Empresa"}

class CompanyUpdate(GroupRequiredMixin, BaseLoginMixin, UpdateView):
    group_required = ['Manager']
    model = Company
    fields = ["name", "description", "cnpj", "manager", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Editar dados da Empresa", "botao": "Atualizar Empresa"}

class CompanyDelete(GroupRequiredMixin, BaseLoginMixin, DeleteView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Excluir Empresa"}

class CompanyList(GroupRequiredMixin, BaseLoginMixin, PaginatedListView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/list/company_list.html"

class CompanyDetail(GroupRequiredMixin, BaseLoginMixin, DetailView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/detail/company_detail.html"


# Client
class ClientCreate(BaseLoginMixin, CreateView):
    model = Client
    fields = ["name", "cnpj_cpf", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Cadastro de Cliente", "botao": "Criar Cliente"}

class ClientUpdate(GroupRequiredMixin, BaseLoginMixin, UpdateView):
    group_required = ['Manager']
    model = Client
    fields = ["name", "cnpj_cpf", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Editar dados do Cliente", "botao": "Atualizar Cliente"}

class ClientDelete(GroupRequiredMixin, BaseLoginMixin, DeleteView):
    group_required = ['Manager']
    model = Client
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Excluir Cliente"}

class ClientList(BaseLoginMixin, PaginatedListView):
    model = Client
    template_name = "cadastros/list/client_list.html"

class ClientDetail(BaseLoginMixin, DetailView):
    model = Client
    template_name = "cadastros/detail/client_detail.html"


# User Profile
class UserProfileCreate(BaseLoginMixin, CreateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Cadastro de Perfil de Usuário", "botao": "Criar Perfil"}

class UserProfileUpdate(BaseLoginMixin, UpdateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Editar dados do Perfil", "botao": "Atualizar Perfil"}

class UserProfileDelete(BaseLoginMixin, DeleteView):
    model = User_Profile
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Excluir Perfil de Usuário"}

class UserProfileList(BaseLoginMixin, PaginatedListView):
    model = User_Profile
    template_name = "cadastros/list/userprofile_list.html"

class UserProfileDetail(BaseLoginMixin, DetailView):
    model = User_Profile
    template_name = "cadastros/detail/userprofile_detail.html"


# Product
class ProductCreate(BaseLoginMixin, CreateView):
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit", "company"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Cadastro de Produto", "botao": "Criar Produto"}

class ProductUpdate(BaseLoginMixin, UpdateView):
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit", "company"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Editar dados do Produto", "botao": "Atualizar Produto"}

class ProductDelete(BaseLoginMixin, DeleteView):
    model = Product
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Excluir Produto"}

class ProductList(BaseLoginMixin, PaginatedListView):
    model = Product
    template_name = "cadastros/list/product_list.html"

class ProductDetail(BaseLoginMixin, DetailView):
    model = Product
    template_name = "cadastros/detail/product_detail.html"


# Order
class OrderCreate(BaseLoginMixin, CreateView):
    model = Order
    fields = ["type", "company", "client", "payment_method", "total_value", "address"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Cadastro de Pedido", "botao": "Criar Pedido"}

class OrderUpdate(BaseLoginMixin, UpdateView):
    model = Order
    fields = ["type", "company", "client", "payment_method", "total_value", "address"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Editar dados do Pedido", "botao": "Atualizar Pedido"}

class OrderDelete(BaseLoginMixin, DeleteView):
    model = Order
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Excluir Pedido"}

class OrderList(BaseLoginMixin, PaginatedListView):
    model = Order
    template_name = "cadastros/list/order_list.html"

class OrderDetail(BaseLoginMixin, DetailView):
    model = Order
    template_name = "cadastros/detail/order_detail.html"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("company", "client", "created_by")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        product_orders = (
            self.object.productorder_set.select_related("product")
            .all()
            .order_by("id")
        )
        context["product_orders"] = product_orders
        context["product_orders_total"] = (
            product_orders.aggregate(total=Sum("total_value")).get("total") or 0
        )
        return context