from django.views.generic import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic import TemplateView

# Buscar a rota da url pelo name dela (urls.py)
from django.urls import reverse_lazy

from .models import Field, Company, User_Profile, Order, Product

# Create your views here.

class IndexView(TemplateView):
    template_name = "cadastros/index.html"




class FieldCreate(CreateView):
    model = Field
    fields = ['name', 'description']
    template_name = 'core/form.html'
    success_url = reverse_lazy('field-list')
    extra_context = {
        'titulo': 'Cadastro de Ramo',
        'botao': 'Criar Ramo'
    }

class FieldUpdate(UpdateView):
    model = Field
    fields = ['name', 'description']
    template_name = 'core/form.html'
    success_url = reverse_lazy('field-list')
    extra_context = {
        'titulo': 'Editar dados do Ramo',
        'botao': 'Atualizar Ramo'
    }

class FieldDelete(DeleteView):
    model = Field
    template_name = 'core/form.html'
    success_url = reverse_lazy('field-list')
    extra_context = {
        'titulo': 'Excluir Ramo',
        'botao': 'Sim, excluir!'
    }

class FieldList(ListView):
    model = Field
    template_name = 'core/list/field.html'
    paginate_by = 20

class FieldDetail(DetailView):
    model = Field
    template_name = 'core/detail/field.html'




class CompanyCreate(CreateView):
    model = Company
    fields = ['field', 'cnpj']
    template_name = 'core/form.html'
    success_url = reverse_lazy('company-list')
    extra_context = {
        'titulo': 'Cadastro de Empresa',
        'botao': 'Criar Empresa'
    }

class CompanyUpdate(UpdateView):
    model = Company
    fields = ['field', 'cnpj']
    template_name = 'core/form.html'
    success_url = reverse_lazy('company-list')
    extra_context = {
        'titulo': 'Editar dados da Empresa',
        'botao': 'Atualizar Empresa'
    }

class CompanyDelete(DeleteView):
    model = Company
    template_name = 'core/form.html'
    success_url = reverse_lazy('company-list')
    extra_context = {
        'titulo': 'Excluir Empresa',
        'botao': 'Sim, excluir!'
    }

class CompanyList(ListView):
    model = Company
    template_name = 'core/list/company.html'
    paginate_by = 20

class CompanyDetail(DetailView):
    model = Company
    template_name = 'core/detail/company.html'




class UserProfileCreate(CreateView):
    model = User_Profile
    fields = ['field', 'phone', 'cpf']
    template_name = 'core/form.html'
    success_url = reverse_lazy('userprofile-list')
    extra_context = {
        'titulo': 'Cadastro de Perfil de Usuário',
        'botao': 'Criar Perfil'
    }

class UserProfileUpdate(UpdateView):
    model = User_Profile
    fields = ['field', 'phone', 'cpf']
    template_name = 'core/form.html'
    success_url = reverse_lazy('userprofile-list')
    extra_context = {
        'titulo': 'Editar dados do Perfil',
        'botao': 'Atualizar Perfil'
    }

class UserProfileDelete(DeleteView):
    model = User_Profile
    template_name = 'core/form.html'
    success_url = reverse_lazy('userprofile-list')
    extra_context = {
        'titulo': 'Excluir Perfil de Usuário',
        'botao': 'Sim, excluir!'
    }

class UserProfileList(ListView):
    model = User_Profile
    template_name = 'core/list/userprofile.html'
    paginate_by = 20

class UserProfileDetail(DetailView):
    model = User_Profile
    template_name = 'core/detail/userprofile.html'




class OrderCreate(CreateView):
    model = Order
    fields = ['company', 'field', 'total_value', 'address']
    template_name = 'core/form.html'
    success_url = reverse_lazy('order-list')
    extra_context = {
        'titulo': 'Cadastro de Pedido',
        'botao': 'Criar Pedido'
    }

class OrderUpdate(UpdateView):
    model = Order
    fields = ['company', 'field', 'total_value', 'address']
    template_name = 'core/form.html'
    success_url = reverse_lazy('order-list')
    extra_context = {
        'titulo': 'Editar dados do Pedido',
        'botao': 'Atualizar Pedido'
    }

class OrderDelete(DeleteView):
    model = Order
    template_name = 'core/form.html'
    success_url = reverse_lazy('order-list')
    extra_context = {
        'titulo': 'Excluir Pedido',
        'botao': 'Sim, excluir!'
    }

class OrderList(ListView):
    model = Order
    template_name = 'core/list/order.html'
    paginate_by = 20

class OrderDetail(DetailView):
    model = Order
    template_name = 'core/detail/order.html'




class ProductCreate(CreateView):
    model = Product
    fields = ['field', 'sku', 'color', 'unit_value', 'stock', 'measure_unit', 'company']
    template_name = 'core/form.html'
    success_url = reverse_lazy('product-list')
    extra_context = {
        'titulo': 'Cadastro de Produto',
        'botao': 'Criar Produto'
    }

class ProductUpdate(UpdateView):
    model = Product
    fields = ['field', 'sku', 'color', 'unit_value', 'stock', 'measure_unit', 'company']
    template_name = 'core/form.html'
    success_url = reverse_lazy('product-list')
    extra_context = {
        'titulo': 'Editar dados do Produto',
        'botao': 'Atualizar Produto'
    }

class ProductDelete(DeleteView):
    model = Product
    template_name = 'core/form.html'
    success_url = reverse_lazy('product-list')
    extra_context = {
        'titulo': 'Excluir Produto',
        'botao': 'Sim, excluir!'
    }

class ProductList(ListView):
    model = Product
    template_name = 'core/list/product.html'
    paginate_by = 20

class ProductDetail(DetailView):
    model = Product
    template_name = 'core/detail/product.html'