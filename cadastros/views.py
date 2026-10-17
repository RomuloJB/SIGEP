from urllib import request

from django import forms
from django.db import models
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.detail import DetailView
from django.urls import reverse, reverse_lazy
from django_filters.views import FilterView
from django.db.models import Sum
from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.functional import cached_property
from django.forms.models import model_to_dict
from django.core.mail import send_mail
from django.template.loader import render_to_string
from collections import Counter

from decimal import Decimal, InvalidOperation
import logging

from .models import Company, Client, User_Profile, Order, Product, ProductOrder
from .forms import UserProfileForm, ClientForm, CompanyForm
from .filters import CompanyFilter, ClientFilter, UserProfileFilter, ProductFilter, OrderFilter, ProductOrderFilter

# Importar o LoginRequiredMixin para proteger as views
from django.contrib.auth.mixins import LoginRequiredMixin
from usuarios.views import ActiveCompanyRequiredMixin, FormErrorMessagesMixin

# Define a permissão de um certo grupo para certas ações
from braces.views import GroupRequiredMixin

logger = logging.getLogger(__name__)


#BaseLogin
class BaseLoginMixin(FormErrorMessagesMixin, LoginRequiredMixin):
    login_url = reverse_lazy('login')

class ConfirmacaoDigitadaForm(forms.Form):
    PALAVRA = "excluir"

    confirmacao = forms.CharField(
        label='Para confirmar, digite "excluir"',
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )

    def clean_confirmacao(self):
        valor = self.cleaned_data["confirmacao"].strip().lower()
        if valor != self.PALAVRA:
            raise forms.ValidationError('Digite "excluir" para confirmar a exclusão.')
        return valor

class ConfirmacaoDigitadaMixin:
    """DeleteView que exige ConfirmacaoDigitadaForm quando exige_confirmacao_digitada() é True."""

    def exige_confirmacao_digitada(self):
        return True

    def get_form_class(self):
        if self.exige_confirmacao_digitada():
            return ConfirmacaoDigitadaForm
        return super().get_form_class()

class ExclusaoProtegidaMixin:
    """
    DeleteView de um registro ainda em uso (FK com on_delete=PROTECT) não estoura 500:
    volta para a página de onde o usuário veio com uma mensagem dizendo o que o prende,
    exibida pelo Bootbox (static/js/mensagens.js).
    """

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError as erro:
            messages.error(self.request, self.mensagem_protegido(erro.protected_objects))
            return redirect(self.url_de_volta())

    def mensagem_protegido(self, protegidos):
        contagem = Counter(obj._meta for obj in protegidos)
        partes = [
            "{} {}".format(qtd, (meta.verbose_name if qtd == 1 else meta.verbose_name_plural).lower())
            for meta, qtd in contagem.items()
        ]
        lista = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
        if sum(contagem.values()) == 1:
            vinculados = "existe {} vinculado".format(lista)
        else:
            vinculados = "existem {} vinculados".format(lista)
        return 'Não é possível excluir "{}": {} a este registro. Exclua esses registros antes.'.format(
            self.object, vinculados
        )

    def url_de_volta(self):
        # Volta para a listagem/detalhe de onde veio; se veio da própria página
        # de exclusão (ou de fora do site), vai para a listagem.
        anterior = self.request.META.get("HTTP_REFERER", "")
        seguro = url_has_allowed_host_and_scheme(
            anterior, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        )
        if seguro and self.request.path not in anterior:
            return anterior
        return self.get_success_url()

class PedidosVisiveisMixin:
    """
    RN02/RF15: o representante só lista, abre, edita, exclui ou duplica os pedidos
    que ele criou; o gerente da empresa ativa enxerga todos (ve_todos_os_pedidos).
    Vem antes do ActiveCompanyRequiredMixin, que já filtra pela empresa.
    """
    campo_autor = "created_by"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.ve_todos_os_pedidos():
            return queryset
        return queryset.filter(**{self.campo_autor: self.request.user})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Itens de pedido: o <select> de pedido só oferece os pedidos visíveis
        if "order" in form.fields:
            form.fields["order"].queryset = self.pedidos_visiveis()
        return form


def notificar_gerentes_novo_pedido(request, pedido):
    """RF07: avisa por e-mail os gerentes da empresa que um pedido foi salvo."""
    destinatarios = list(
        pedido.company.manager.exclude(pk=pedido.created_by_id)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not destinatarios:
        return

    contexto = {
        "pedido": pedido,
        "itens": pedido.product_orders.select_related("product"),
        "url": request.build_absolute_uri(reverse("order-detail", args=[pedido.pk])),
    }
    assunto = "Novo pedido #{} — {}".format(pedido.pk, pedido.client.name)
    corpo = render_to_string("cadastros/email/novo_pedido.txt", contexto)
    try:
        send_mail(assunto, corpo, None, destinatarios)
    except Exception:
        # O pedido já foi gravado: falha no SMTP fica no log, não vira erro 500
        logger.exception("Falha ao enviar o e-mail do pedido #%s aos gerentes", pedido.pk)


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
        context["total_orders"] = self.pedidos_visiveis().count()
        return context
    

# Listas Paginadas e com filtros de busca (django-filter)
# FilterView faz o papel da ListView e ainda aplica o filterset_class por cima do get_queryset
class PaginatedFilterView(FilterView):
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
        # Quantos filtros estão preenchidos, para o badge do botão "Filtros"
        form = self.filterset.form
        if form.is_valid():
            context["active_filters"] = sum(
                1 for value in form.cleaned_data.values() if value not in (None, "", [])
            )
        return context

# Company
class CompanyCreate(GroupRequiredMixin, BaseLoginMixin, CreateView):
    group_required = ['Manager']
    model = Company
    form_class = CompanyForm
    template_name = "cadastros/company_form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Cadastro de Empresa", "botao": "Criar Empresa"}

    # Override do método form_valid para definir o usuário logado como o gerente da empresa criada
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self.object.manager.add(self.request.user)  # Adiciona o usuário logado como gerente após salvar o ID
        self.object.manager.add(*User.objects.filter(is_superuser=True))
        return response

class CompanyUpdate(GroupRequiredMixin, BaseLoginMixin, UpdateView):
    group_required = ['Manager']
    model = Company
    form_class = CompanyForm
    template_name = "cadastros/company_form.html"
    success_url = reverse_lazy("company-list")
    extra_context = {"title": "Editar dados da Empresa", "botao": "Atualizar Empresa"}

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(manager=self.request.user).distinct()

    def form_valid(self, form):
        if self.request.user not in form.instance.manager.all():
            form.instance.manager.add(self.request.user)
        response = super().form_valid(form)
        # Superusuários nunca podem ser removidos como gerentes,
        # mesmo que tenham sido removidos da seleção por outro manager
        self.object.manager.add(*User.objects.filter(is_superuser=True))
        # Editou a empresa ativa: atualiza o nome exibido no cabeçalho
        if self.request.session.get('active_company_id') == self.object.pk:
            self.request.session['company_name'] = self.object.display_name
        return response

class CompanyDelete(ExclusaoProtegidaMixin, ConfirmacaoDigitadaMixin, GroupRequiredMixin, BaseLoginMixin, DeleteView):
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

class CompanyList(GroupRequiredMixin, BaseLoginMixin, PaginatedFilterView):
    group_required = ['Manager']
    model = Company
    template_name = "cadastros/list/company_list.html"
    ordering = ['name']
    filterset_class = CompanyFilter

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
    form_class = ClientForm
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
    form_class = ClientForm
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Editar dados do Cliente", "botao": "Atualizar Cliente"}
    
class ClientDelete(ExclusaoProtegidaMixin, GroupRequiredMixin, ActiveCompanyRequiredMixin, DeleteView):
    group_required = ['Manager']
    model = Client
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("client-list")
    extra_context = {"title": "Excluir Cliente"}

class ClientList(ActiveCompanyRequiredMixin, PaginatedFilterView):
    model = Client
    template_name = "cadastros/list/client_list.html"
    ordering = ['name']
    filterset_class = ClientFilter
    
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
    form_class = UserProfileForm
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Cadastro de Perfil de Usuário", "botao": "Criar Perfil"}

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class UserProfileUpdate(BaseLoginMixin, UpdateView):
    model = User_Profile
    form_class = UserProfileForm
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

class UserProfileDelete(ExclusaoProtegidaMixin, ConfirmacaoDigitadaMixin, BaseLoginMixin, DeleteView):
    model = User_Profile
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("userprofile-list")
    extra_context = {"title": "Excluir Perfil de Usuário"}

    def exige_confirmacao_digitada(self):
        # Só o perfil de um gerente é exclusão perigosa
        return self.object.is_manager

class UserProfileList(BaseLoginMixin, PaginatedFilterView):
    model = User_Profile
    template_name = "cadastros/list/userprofile_list.html"
    ordering = ['name']
    filterset_class = UserProfileFilter

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

class ProductDelete(ExclusaoProtegidaMixin, GroupRequiredMixin, ActiveCompanyRequiredMixin, DeleteView):
    group_required = ['Manager']
    model = Product
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("product-list")
    extra_context = {"title": "Excluir Produto"}

class ProductList(ActiveCompanyRequiredMixin, PaginatedFilterView):
    model = Product
    template_name = "cadastros/list/product_list.html"
    ordering = ['name']
    filterset_class = ProductFilter
    
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
        # Linhas que o order-scripts.js monta ao abrir a tela
        context["itens_iniciais"] = self.itens_iniciais()
        return context

    def itens_iniciais(self):
        # Ao voltar com erro, a tabela de itens é remontada com o que foi enviado
        if self.request.method != "POST":
            return []
        return [
            {"product_id": pid, "quantity": qty, "discount": disc}
            for pid, qty, disc in zip(
                self.request.POST.getlist("product_id[]"),
                self.request.POST.getlist("quantity[]"),
                self.request.POST.getlist("discount[]"),
            )
        ]

    @transaction.atomic
    def form_valid(self, form):
        form.instance.created_by = self.request.user

        product_ids = self.request.POST.getlist("product_id[]")
        quantities = self.request.POST.getlist("quantity[]")
        discounts = self.request.POST.getlist("discount[]")

        items = []
        errors = []

        for pid, qty_str, disc_str in zip(product_ids, quantities, discounts):
            try:
                product = Product.objects.select_for_update().get(pk=int(pid), company=self.active_company)
            except (Product.DoesNotExist, ValueError):
                errors.append(f"Produto inválido (id={pid}).")
                continue

            try:
                qty = int(qty_str)
                if qty <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"Quantidade inválida para o produto '{product.name}'.")
                continue

            try:
                discount = Decimal(disc_str) if disc_str else Decimal("0")
                if discount < 0:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                errors.append(f"Desconto inválido para o produto '{product.name}'.")
                continue

            if (product.stock or 0) < qty:
                errors.append(
                    f"Estoque insuficiente para '{product.name}': "
                    f"disponível {product.stock}, solicitado {qty}."
                )
                continue

            subtotal = product.unit_value * qty
            if discount > subtotal:
                errors.append(f"Desconto maior que o valor do item '{product.name}'.")
                continue

            items.append((product, qty, discount, subtotal - discount))

        if errors:
            form.add_error(None, " | ".join(errors))
            return self.form_invalid(form)

        if not items:
            form.add_error(None, "Adicione pelo menos um produto ao pedido.")
            return self.form_invalid(form)

        total = sum(line_total for _, _, _, line_total in items)
        form.instance.total_value = total
        response = super().form_valid(form)

        for product, qty, discount, line_total in items:
            ProductOrder.objects.create(
                order=self.object,
                product=product,
                quantity=qty,
                unit_value=product.unit_value or 0,
                discount=discount,
                total_value=line_total,
            )
            product.stock = (product.stock or 0) - qty
            product.save(update_fields=["stock"])

        # Só depois do commit: se o pedido falhar, nenhum gerente é avisado
        pedido = self.object
        transaction.on_commit(lambda: notificar_gerentes_novo_pedido(self.request, pedido))

        return response

class OrderDuplicate(PedidosVisiveisMixin, OrderCreate):
    """
    RF12: abre o formulário de novo pedido já preenchido com o cabeçalho e os itens
    de um pedido existente. Salvar passa pelas validações do OrderCreate (estoque,
    desconto, valor atual do produto) e cria outro pedido; o original não muda.
    """

    @cached_property
    def original(self):
        # get_queryset já aplica empresa ativa e RN02: pedido alheio dá 404
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_initial(self):
        return model_to_dict(self.original, fields=self.fields)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Duplicar Pedido #{}".format(self.original.pk)
        context["pedido_original"] = self.original
        return context

    def itens_iniciais(self):
        if self.request.method == "POST":
            return super().itens_iniciais()
        # Mesmo produto em mais de uma linha (itens lançados pela tela "Itens de
        # Pedido") vira uma linha só, porque o formulário não aceita repetidos
        itens = {}
        for item in self.original.product_orders.exclude(product=None).order_by("id"):
            linha = itens.setdefault(item.product_id, {"product_id": item.product_id, "quantity": 0, "discount": Decimal("0")})
            linha["quantity"] += item.quantity
            linha["discount"] += item.discount
        return list(itens.values())

class OrderUpdate(PedidosVisiveisMixin, ActiveCompanyRequiredMixin, UpdateView):
    model = Order
    fields = ["type", "client", "payment_method", "address", "city", "uf"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Editar dados do Pedido", "botao": "Atualizar Pedido"}

class OrderDelete(PedidosVisiveisMixin, ExclusaoProtegidaMixin, ActiveCompanyRequiredMixin, DeleteView):
    model = Order
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("order-list")
    extra_context = {"title": "Excluir Pedido"}

class OrderList(PedidosVisiveisMixin, ActiveCompanyRequiredMixin, PaginatedFilterView):
    model = Order
    template_name = "cadastros/list/order_list.html"
    ordering = ['-id']
    filterset_class = OrderFilter

    def get_queryset(self):
        # A tabela mostra o cliente de cada pedido
        return super().get_queryset().select_related("client")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_orders"] = self.get_queryset().count()
        return context

class OrderDetail(PedidosVisiveisMixin, ActiveCompanyRequiredMixin, DetailView):
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
            self.object.product_orders.select_related("product")
            .all()
            .order_by("id")
        )
        context["product_orders"] = product_orders
        context["product_orders_total"] = (
            product_orders.aggregate(total=Sum("total_value")).get("total") or 0
        )
        return context


# ─── ProductOrder ──────────────────────────────────────────────────────────────

class ItensVisiveisMixin(PedidosVisiveisMixin):
    # Itens seguem a RN02 pelo autor do pedido a que pertencem
    campo_autor = "order__created_by"

class ProductOrderCreate(ItensVisiveisMixin, ActiveCompanyRequiredMixin, CreateView):
    model = ProductOrder
    fields = ["order", "product", "quantity", "unit_value", "discount"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Cadastro de Item de Pedido", "botao": "Criar Item"}

    def form_valid(self, form):
        quantity = form.cleaned_data.get('quantity', 0)
        unit_value = form.cleaned_data.get('unit_value', 0)
        discount = form.cleaned_data.get('discount') or 0
        form.instance.total_value = (quantity * unit_value) - discount
        return super().form_valid(form)


class ProductOrderUpdate(ItensVisiveisMixin, ActiveCompanyRequiredMixin, UpdateView):
    model = ProductOrder
    fields = ["order", "product", "quantity", "unit_value", "discount"]
    template_name = "cadastros/form.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Editar dados do Item de Pedido", "botao": "Atualizar Item"}

    def form_valid(self, form):
        quantity = form.cleaned_data.get('quantity', 0)
        unit_value = form.cleaned_data.get('unit_value', 0)
        discount = form.cleaned_data.get('discount') or 0
        form.instance.total_value = (quantity * unit_value) - discount
        return super().form_valid(form)
    

class ProductOrderDelete(ItensVisiveisMixin, ExclusaoProtegidaMixin, ActiveCompanyRequiredMixin, DeleteView):
    model = ProductOrder
    template_name = "cadastros/form_delete.html"
    success_url = reverse_lazy("productorder-list")
    extra_context = {"title": "Excluir Item de Pedido"}


class ProductOrderList(ItensVisiveisMixin, ActiveCompanyRequiredMixin, PaginatedFilterView):
    model = ProductOrder
    template_name = "cadastros/list/productorder_list.html"
    ordering = ['id']
    filterset_class = ProductOrderFilter

    def get_queryset(self):
        # A tabela mostra o pedido, o cliente do pedido e o produto de cada item
        return super().get_queryset().select_related("order__client", "product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_items"] = self.get_queryset().count()
        return context


class ProductOrderDetail(ItensVisiveisMixin, ActiveCompanyRequiredMixin, DetailView):
    model = ProductOrder
    template_name = "cadastros/detail/productorder_detail.html"