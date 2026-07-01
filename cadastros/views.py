from urllib import request

from django.db import models
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.urls import reverse_lazy
from django.db.models import Sum
from django.db import transaction
from django.http import JsonResponse
from django.views import View

from .models import Company, Client, User_Profile, Order, Product, ProductOrder

# Importar o LoginRequiredMixin para proteger as views
from django.contrib.auth.mixins import LoginRequiredMixin
from usuarios.views import ActiveCompanyRequiredMixin

# Define a permissão de um certo grupo para certas ações
from braces.views import GroupRequiredMixin


#BaseLogin
class BaseLoginMixin(LoginRequiredMixin):
    login_url = reverse_lazy('login')


# View que lista as ccompanhias para o usuário que pertence ao sales_rep veja e ative ela na sessão
# Essa View adiciona na sessão o ID da company e um objeto self.company_active na view, sendo usado
# como herança para outras views que precisam da company ativa do usuário. A company ativa é a primeira company que o usuário tem acesso, seja como gerente ou como representante de vendas.


class IndexView(ActiveCompanyRequiredMixin, TemplateView):
    template_name = "cadastros/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Exibe os totais relacionados à empresa ativa selecionada
        context["total_clients"] = Client.objects.filter(company=self.active_company).count()
        context["total_products"] = Product.objects.filter(company=self.active_company).count()
        context["total_orders"] = Order.objects.filter(company=self.active_company).count()
        return context
    

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
    fields = ["name", "description", "cnpj", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Cadastro de Empresa", "botao": "Criar Empresa"}

    # Override do método form_valid para definir o usuário logado como o gerente da empresa criada
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self.object.manager.add(self.request.user)  # Adiciona o usuário logado como gerente após salvar o ID
        return response

class CompanyUpdate(GroupRequiredMixin, BaseLoginMixin, UpdateView):
    group_required = ['Manager']
    model = Company
    # manager fica aqui pois pode ter mais de um gerente. 
    fields = ["name", "description", "cnpj", "manager", "sales_rep"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Editar dados da Empresa", "botao": "Atualizar Empresa"}

    def get_queryset(self):
        qs = super().get_queryset()

        if self.request.user.is_superuser:
            return qs

        return qs.filter(manager=self.request.user).distinct()

    # No form_valid, não remova o created_by do manager, mas outras pessoas podem ser removidas
    def form_valid(self, form):
        # Garante que o usuário logado permaneça como gerente
        if self.request.user not in form.instance.manager.all():
            form.instance.manager.add(self.request.user)
        return super().form_valid(form)
    

class CompanyDelete(GroupRequiredMixin, BaseLoginMixin, DeleteView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Excluir Empresa"}

    def get_queryset(self):
        qs = super().get_queryset()

        if self.request.user.is_superuser:
            return qs

        return qs.filter(manager=self.request.user).distinct()

class CompanyList(GroupRequiredMixin, BaseLoginMixin, PaginatedListView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/list/company_list.html"

    def get_queryset(self):
        qs = super().get_queryset()

        if self.request.user.is_superuser:
            return qs

        return qs.filter(manager=self.request.user).distinct()

class CompanyDetail(GroupRequiredMixin, BaseLoginMixin, DetailView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/detail/company_detail.html"

    def get_queryset(self):
        qs = super().get_queryset()

        if self.request.user.is_superuser:
            return qs

        return qs.filter(manager=self.request.user).distinct()


# Client
class ClientCreate(ActiveCompanyRequiredMixin, CreateView):
    model = Client
    fields = ["name", "cnpj_cpf", "address", "city", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Cadastro de Cliente", "botao": "Criar Cliente"}

    def get_success_url(self):
        return reverse_lazy("client-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class ClientUpdate(ActiveCompanyRequiredMixin, UpdateView):
    model = Client
    fields = ["name", "cnpj_cpf", "address", "city", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Editar dados do Cliente", "botao": "Atualizar Cliente"}
    
class ClientDelete(GroupRequiredMixin, ActiveCompanyRequiredMixin, DeleteView):
    group_required = ['Manager']
    model = Client
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Excluir Cliente"}

class ClientList(ActiveCompanyRequiredMixin, PaginatedListView):
    model = Client
    template_name = "cadastros/list/client_list.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_clients"] = self.get_queryset().count()
        return context

class ClientDetail(ActiveCompanyRequiredMixin, DetailView):
    model = Client
    template_name = "cadastros/detail/client_detail.html"


# User Profile
class UserProfileCreate(BaseLoginMixin, CreateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Cadastro de Perfil de Usuário", "botao": "Criar Perfil"}

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class UserProfileUpdate(BaseLoginMixin, UpdateView):
    model = User_Profile
    fields = ["name", "phone", "cpf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Editar dados do Perfil", "botao": "Atualizar Perfil"}

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        if pk:
            try:
                profile = User_Profile.objects.get(pk=pk)
                if profile.user == self.request.user:
                    profile, created = User_Profile.objects.get_or_create(
                        user=self.request.user,
                        defaults={
                            "name": self.request.user.get_full_name() or self.request.user.username,
                            "phone": "",
                            "cpf": ""
                        }
                    )
                return profile
            except User_Profile.DoesNotExist:
                pass
        
        profile, created = User_Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "name": self.request.user.get_full_name() or self.request.user.username,
                "phone": "",
                "cpf": ""
            }
        )
        return profile

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

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        if pk:
            try:
                profile = User_Profile.objects.get(pk=pk)
                if profile.user == self.request.user:
                    profile, created = User_Profile.objects.get_or_create(
                        user=self.request.user,
                        defaults={
                            "name": self.request.user.get_full_name() or self.request.user.username,
                            "phone": "",
                            "cpf": ""
                        }
                    )
                return profile
            except User_Profile.DoesNotExist:
                pass

        profile, created = User_Profile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "name": self.request.user.get_full_name() or self.request.user.username,
                "phone": "",
                "cpf": ""
            }
        )
        return profile


# Product
class ProductCreate(GroupRequiredMixin, ActiveCompanyRequiredMixin, CreateView):
    group_required = ['Manager']
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Cadastro de Produto", "botao": "Criar Produto"}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class ProductUpdate(GroupRequiredMixin, ActiveCompanyRequiredMixin, UpdateView):
    group_required = ['Manager']
    model = Product
    fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Editar dados do Produto", "botao": "Atualizar Produto"}

class ProductDelete(GroupRequiredMixin, ActiveCompanyRequiredMixin, DeleteView):
    group_required = ['Manager']
    model = Product
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Excluir Produto"}

class ProductList(ActiveCompanyRequiredMixin, PaginatedListView):
    model = Product
    template_name = "cadastros/list/product_list.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_products"] = self.get_queryset().count()
        return context

class ProductDetail(ActiveCompanyRequiredMixin, DetailView):
    model = Product
    template_name = "cadastros/detail/product_detail.html"


# ─── API: retorna dados de um produto por pk ───────────────────────────────────
class ProductDataView(ActiveCompanyRequiredMixin, View):
    """Retorna JSON com dados de um produto para uso no formulário de pedido."""

    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, company=self.active_company)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Produto não encontrado."}, status=404)

        return JsonResponse({
            "id": product.pk,
            "name": product.name,
            "sku": product.sku,
            "unit_value": product.unit_value or 0,
            "stock": product.stock or 0,
            "measure_unit": product.get_measure_unit_display(),
        })


# ─── Order ─────────────────────────────────────────────────────────────────────

class OrderCreate(ActiveCompanyRequiredMixin, CreateView):
    model = Order
    fields = ["type", "client", "payment_method", "address", "city", "uf"]
    template_name = "cadastros/order_form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Cadastro de Pedido", "botao": "Criar Pedido"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Envia a lista de produtos disponíveis da empresa ativa para o template popular o <select>
        context["products"] = Product.objects.filter(company=self.active_company).order_by("name")
        return context

    @transaction.atomic
    def form_valid(self, form):
        form.instance.created_by = self.request.user

        # Coleta os itens enviados pelo formulário dinâmico
        product_ids = self.request.POST.getlist("product_id[]")
        quantities = self.request.POST.getlist("quantity[]")

        items = []
        errors = []

        for pid, qty_str in zip(product_ids, quantities):
            try:
                # Restringir produtos à empresa ativa por segurança
                product = Product.objects.select_for_update().get(pk=int(pid), company=self.active_company)
            except (Product.DoesNotExist, ValueError):
                errors.append(f"Produto inválido (id={pid}).")
                continue

            try:
                qty = int(qty_str)
                if qty <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"Quantidade inválida para o produto '{product.name}'.")
                continue

            if (product.stock or 0) < qty:
                errors.append(
                    f"Estoque insuficiente para '{product.name}': "
                    f"disponível {product.stock}, solicitado {qty}."
                )
                continue

            items.append((product, qty))

        if errors:
            # Devolve o formulário com as mensagens de erro
            form.add_error(None, " | ".join(errors))
            return self.form_invalid(form)

        if not items:
            form.add_error(None, "Adicione pelo menos um produto ao pedido.")
            return self.form_invalid(form)

        # Calcula o total e salva o Order
        total = sum(p.unit_value * q for p, q in items)
        form.instance.total_value = total
        response = super().form_valid(form)  # salva self.object

        # Cria os ProductOrder e baixa o estoque
        for product, qty in items:
            unit_val = product.unit_value or 0
            ProductOrder.objects.create(
                order=self.object,
                product=product,
                quantity=qty,
                unit_value=unit_val,
                total_value=unit_val * qty,
            )
            product.stock = (product.stock or 0) - qty
            product.save(update_fields=["stock"])

        return response


class OrderUpdate(ActiveCompanyRequiredMixin, UpdateView):
    model = Order
    fields = ["type", "client", "payment_method", "address", "city", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Editar dados do Pedido", "botao": "Atualizar Pedido"}

class OrderDelete(ActiveCompanyRequiredMixin, DeleteView):
    model = Order
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Excluir Pedido"}

class OrderList(ActiveCompanyRequiredMixin, PaginatedListView):
    model = Order
    template_name = "cadastros/list/order_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_orders"] = self.get_queryset().count()
        return context

class OrderDetail(ActiveCompanyRequiredMixin, DetailView):
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


# ─── ProductOrder ──────────────────────────────────────────────────────────────

class ProductOrderCreate(ActiveCompanyRequiredMixin, CreateView):
    model = ProductOrder
    fields = ["order", "product", "quantity", "unit_value"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Cadastro de Item de Pedido", "botao": "Criar Item"}

    def form_valid(self, form):
        quantity = form.cleaned_data.get('quantity', 0)
        unit_value = form.cleaned_data.get('unit_value', 0)
        form.instance.total_value = quantity * unit_value
        return super().form_valid(form)


class ProductOrderUpdate(ActiveCompanyRequiredMixin, UpdateView):
    model = ProductOrder
    fields = ["order", "product", "quantity", "unit_value"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Editar dados do Item de Pedido", "botao": "Atualizar Item"}

    def form_valid(self, form):
        quantity = form.cleaned_data.get('quantity', 0)
        unit_value = form.cleaned_data.get('unit_value', 0)
        form.instance.total_value = quantity * unit_value
        return super().form_valid(form)


class ProductOrderDelete(ActiveCompanyRequiredMixin, DeleteView):
    model = ProductOrder
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Excluir Item de Pedido"}


class ProductOrderList(ActiveCompanyRequiredMixin, PaginatedListView):
    model = ProductOrder
    template_name = "cadastros/list/productorder_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_items"] = self.get_queryset().count()
        return context


class ProductOrderDetail(ActiveCompanyRequiredMixin, DetailView):
    model = ProductOrder
    template_name = "cadastros/detail/productorder_detail.html"