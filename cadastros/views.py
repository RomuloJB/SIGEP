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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_clients"] = Client.objects.count()
        context["total_products"] = Product.objects.count()
        context["total_orders"] = Order.objects.count()
        return context

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

    def get_success_url(self):
        # Redirecionar para a página de detalhes do cliente criado passando o pk
        return reverse_lazy("client-detail", kwargs={"pk": self.object.pk}) # kwargs significa "keyword arguments" ou "argumentos de palavra-chave", e é usado para passar argumentos nomeados para a função reverse_lazy. Nesse caso, estamos passando o pk do objeto criado para a URL de detalhes do cliente.

    def form_valid(self, form):
        # atribuir o usuário logado ao campo created_by do modelo Client
        form.instance.created_by = self.request.user
        # executa a criacao do objeto e faz o insert no banco
        url_success = super().form_valid(form)
        # a partir daqui consigo acessar o objeto criado atraves do self.object
        # print(self.object)
        # self.object.name = "Ok - " + self.object.name
        # self.object.save()

        return url_success

class ClientUpdate(GroupRequiredMixin, BaseLoginMixin, UpdateView):
    group_required = ['Manager']
    model = Client
    fields = ["name", "cnpj_cpf", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Editar dados do Cliente", "botao": "Atualizar Cliente"}

    def get_queryset(self):
        # queryset são consultas no banco de dados
        return super().get_queryset().filter(created_by=self.request.user)
    
class ClientDelete(GroupRequiredMixin, BaseLoginMixin, DeleteView):
    group_required = ['Manager']
    model = Client
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Excluir Cliente"}

    def get_queryset(self):
        # queryset são consultas no banco de dados
        return super().get_queryset().filter(created_by=self.request.user)

class ClientList(BaseLoginMixin, PaginatedListView):
    model = Client
    template_name = "cadastros/list/client_list.html"

    def get_queryset(self):
        # queryset são consultas no banco de dados
        return super().get_queryset().filter(created_by=self.request.user)
    
    # Sobrescreve o método get_context_data para adicionar um novo contexto ao template, no caso, o total de clientes
    # agora podemos mostrar o total de clientes na página de listagem de clientes, usando {{ total_clients }} no template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_clients"] = self.get_queryset().count()
        return context

class ClientDetail(BaseLoginMixin, DetailView):
    model = Client
    template_name = "cadastros/detail/client_detail.html"

    def get_queryset(self):
        # queryset são consultas no banco de dados
        return super().get_queryset().filter(created_by=self.request.user)


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

    def get_queryset(self):
        return super().get_queryset().filter(company__manager=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_products"] = self.get_queryset().count()
        return context

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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['client'].queryset = Client.objects.filter(created_by=self.request.user)
        return form

class OrderUpdate(BaseLoginMixin, UpdateView):
    model = Order
    fields = ["type", "company", "client", "payment_method", "total_value", "address"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Editar dados do Pedido", "botao": "Atualizar Pedido"}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['client'].queryset = Client.objects.filter(created_by=self.request.user)
        return form

class OrderDelete(BaseLoginMixin, DeleteView):
    model = Order
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Excluir Pedido"}

class OrderList(BaseLoginMixin, PaginatedListView):
    model = Order
    template_name = "cadastros/list/order_list.html"

    def get_queryset(self):
        return super().get_queryset().filter(company__manager=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_orders"] = self.get_queryset().count()
        return context

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