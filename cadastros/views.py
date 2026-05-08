from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.urls import reverse_lazy
from django.db.models import Sum

from .models import Company, Client, User_Profile, Order, Product


class IndexView(TemplateView):
    template_name = "cadastros/index.html"


# Company
class CompanyCreate(CreateView):
    model = Company
    fields = ["name", "description", "cnpj", "manager", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Cadastro de Empresa", "botao": "Criar Empresa"}

class CompanyUpdate(UpdateView):
    model = Company
    fields = ["name", "description", "cnpj", "manager", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Editar dados da Empresa", "botao": "Atualizar Empresa"}

class CompanyDelete(DeleteView):
    model = Company
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Excluir Empresa", "botao": "Sim, excluir!"}

class CompanyList(ListView):
    model = Company
    template_name = "cadastros/list/company_list.html"
    paginate_by = 20

class CompanyDetail(DetailView):
    model = Company
    template_name = "cadastros/detail/company.html"


# Client
class ClientCreate(CreateView):
    model = Client
    fields = ["name", "cnpj_cpf", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Cadastro de Cliente", "botao": "Criar Cliente"}

class ClientUpdate(UpdateView):
    model = Client
    fields = ["name", "cnpj_cpf", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Editar dados do Cliente", "botao": "Atualizar Cliente"}

class ClientDelete(DeleteView):
    model = Client
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Excluir Cliente", "botao": "Sim, excluir!"}

class ClientList(ListView):
    model = Client
    template_name = "cadastros/list/client_list.html"
    paginate_by = 20

class ClientDetail(DetailView):
    model = Client
    template_name = "cadastros/detail/client.html"


# User Profile
class UserProfileCreate(CreateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Cadastro de Perfil de Usuário", "botao": "Criar Perfil"}

class UserProfileUpdate(UpdateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Editar dados do Perfil", "botao": "Atualizar Perfil"}

class UserProfileDelete(DeleteView):
    model = User_Profile
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Excluir Perfil de Usuário", "botao": "Sim, excluir!"}

class UserProfileList(ListView):
    model = User_Profile
    template_name = "cadastros/list/userprofile_list.html"
    paginate_by = 20

class UserProfileDetail(DetailView):
    model = User_Profile
    template_name = "cadastros/detail/userprofile.html"


# Product
class ProductCreate(CreateView):
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit", "company"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Cadastro de Produto", "botao": "Criar Produto"}

class ProductUpdate(UpdateView):
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit", "company"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Editar dados do Produto", "botao": "Atualizar Produto"}

class ProductDelete(DeleteView):
    model = Product
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Excluir Produto", "botao": "Sim, excluir!"}

class ProductList(ListView):
    model = Product
    template_name = "cadastros/list/product_list.html"
    paginate_by = 20

class ProductDetail(DetailView):
    model = Product
    template_name = "cadastros/detail/product.html"


# Order
class OrderCreate(CreateView):
    model = Order
    fields = ["type", "company", "client", "payment_method", "total_value", "address"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Cadastro de Pedido", "botao": "Criar Pedido"}

class OrderUpdate(UpdateView):
    model = Order
    fields = ["type", "company", "client", "payment_method", "total_value", "address"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Editar dados do Pedido", "botao": "Atualizar Pedido"}

class OrderDelete(DeleteView):
    model = Order
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Excluir Pedido", "botao": "Sim, excluir!"}

class OrderList(ListView):
    model = Order
    template_name = "cadastros/list/order_list.html"
    paginate_by = 20

class OrderDetail(DetailView):
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