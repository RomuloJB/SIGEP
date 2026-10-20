from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from cadastros.models import Company, User_Profile
from cadastros.forms import PhoneField, CPFField

class FormErrorMessagesMixin:
    """
    Traduz a mensagem padrão do Django para campo obrigatório ("This field is required.").
    O projeto roda com LANGUAGE_CODE='en-us' — mudar para pt-br alteraria a formatação
    de números nos templates (ex.: data-price="12,50" quebraria o JS do pedido).
    """
    required_error_message = "Este campo é obrigatório."

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.error_messages["required"] = self.required_error_message
        return form


class BaseLoginMixin(FormErrorMessagesMixin, LoginRequiredMixin):
    login_url = reverse_lazy('login')


def activate_company(request, company):
    """Grava a empresa escolhida na sessão e manda para o dashboard."""
    request.session['active_company_id'] = company.id
    request.session['company_name'] = company.name
    return redirect('index')


class SelectCompanyView(BaseLoginMixin, ListView):
    """
    Exibe a lista de empresas às quais o usuário logado tem acesso
    (seja como gerente ou como representante de vendas).
    Com uma única empresa não há o que escolher: ela é ativada direto.
    """
    model = Company
    template_name = "usuarios/select_company.html"
    context_object_name = "companies"

    def get(self, request, *args, **kwargs):
        companies = list(self.get_queryset()[:2])
        if len(companies) == 1:
            return activate_company(request, companies[0])
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Company.objects.all()
        return Company.objects.filter(
            Q(manager=self.request.user) | Q(sales_rep=self.request.user)
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Verifica se o usuário é gerente ou superusuário para exibir opção de cadastro de empresa
        context['is_manager'] = self.request.user.groups.filter(name='Manager').exists() or self.request.user.is_superuser
        return context


class ActivateCompanyView(BaseLoginMixin, View):
    """
    Ativa a empresa selecionada pelo usuário salvando seu ID e nome na sessão.
    """
    def get(self, request, pk):
        if request.user.is_superuser:
            company = get_object_or_404(Company, pk=pk)
        else:
            company = get_object_or_404(
                Company.objects.filter(
                    Q(manager=request.user) | Q(sales_rep=request.user)
                ).distinct(),
                pk=pk
            )
            
        return activate_company(request, company)

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
            if request.user.is_superuser:
                self.active_company = Company.objects.get(pk=active_company_id)
            else:
                self.active_company = Company.objects.filter(
                    Q(manager=request.user) | Q(sales_rep=request.user)
                ).distinct().get(pk=active_company_id)
        except Company.DoesNotExist:
            if 'active_company_id' in request.session:
                del request.session['active_company_id']
            if 'company_name' in request.session:
                del request.session['company_name']
            return redirect('select-company')
        return super().dispatch(request, *args, **kwargs)

    def ve_todos_os_pedidos(self):
        # RN02: gerente da empresa ativa (ou superusuário) vê todos os pedidos dela;
        # representante vê só os que ele criou.
        user = self.request.user
        return user.is_superuser or self.active_company.manager.filter(pk=user.pk).exists()

    def pedidos_visiveis(self):
        from cadastros.models import Order
        pedidos = Order.objects.filter(company=self.active_company)
        if self.ve_todos_os_pedidos():
            return pedidos
        return pedidos.filter(created_by=self.request.user)

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
        # DeleteView usa um Form simples (sem .instance), então não há nada
        # a associar à empresa ativa nesse caso — o objeto já existe.
        if hasattr(form, 'instance'):
            # Associa automaticamente o objeto à empresa ativa na criação/atualização
            if hasattr(form.instance.__class__, 'company') and not getattr(form.instance, 'company', None):
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


# ─── Usuários: login + perfil (nome, telefone, CPF) editados juntos ───────────
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import UpdateView

class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class UserProfileFieldsForm(forms.ModelForm):
    """
    Formulário de User que também grava o User_Profile ligado a ele, para que o
    login e os dados pessoais da mesma pessoa sejam mantidos numa tela só.
    """
    email = forms.EmailField(label="E-mail")
    name = forms.CharField(max_length=100, label="Nome completo")
    phone = PhoneField(label="Telefone")
    cpf = CPFField(label="CPF")

    profile_fields = ("name", "phone", "cpf")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Usuários criados pelo createsuperuser ainda não têm perfil
        profile = getattr(self.instance, "profile", None)
        if profile:
            for field in self.profile_fields:
                self.initial[field] = getattr(profile, field)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este e-mail já está em uso por outro usuário.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            User_Profile.objects.update_or_create(
                user=user,
                defaults={field: self.cleaned_data[field] for field in self.profile_fields},
            )
        return user


class UserManageForm(UserProfileFieldsForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos / Permissões"
    )

    class Meta:
        model = User
        fields = ["username", "email", "is_active", "is_superuser", "groups"]

    field_order = ["username", "email", "name", "phone", "cpf", "is_active", "is_superuser", "groups"]


class UserCreateForm(UserManageForm, UserCreationForm):
    """Cadastro pelo superusuário: campos do UserManageForm + senha validada pelo Django."""
    field_order = ["username", "email", "name", "phone", "cpf", "password1", "password2",
                   "is_active", "is_superuser", "groups"]


class UserRegisterForm(UserProfileFieldsForm, UserCreationForm):
    """Cadastro público (Sign Up): cria o login e o perfil de uma vez."""
    class Meta(UserCreationForm.Meta):
        fields = ["username", "email"]

    field_order = ["username", "email", "name", "phone", "cpf", "password1", "password2"]


class MyProfileForm(UserProfileFieldsForm):
    """Dados que o próprio usuário pode alterar em "Meu perfil"."""
    class Meta:
        model = User
        fields = ["email"]

    field_order = ["name", "email", "phone", "cpf"]


# ─── Gerenciamento de Usuários (Apenas Superuser) ─────────────────────────────

class UserListView(SuperuserRequiredMixin, ListView):
    model = User
    template_name = "usuarios/user_list.html"
    context_object_name = "users"
    queryset = User.objects.select_related("profile").prefetch_related("groups").order_by("username")
    paginate_by = 10
    paginate_by_options = (10, 20, 40)

    def get_paginate_by(self, queryset):
        # Mesmo ?per_page=10|20|40 das listagens de cadastros (cadastros/paginacao.html)
        per_page = self.request.GET.get("per_page", "")
        return int(per_page) if per_page.isdigit() and int(per_page) in self.paginate_by_options else self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page_options"] = self.paginate_by_options
        return context


class UserCreateView(SuperuserRequiredMixin, FormErrorMessagesMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "usuarios/user_form.html"
    success_url = reverse_lazy("user-list")
    success_message = 'Usuário "%(username)s" cadastrado com sucesso.'
    extra_context = {
        "title": "Novo Usuário",
        "subtitle": "Cadastre o acesso, os dados pessoais e as permissões do novo usuário.",
        "botao": "Cadastrar Usuário",
    }


class UserUpdateView(SuperuserRequiredMixin, FormErrorMessagesMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserManageForm
    template_name = "usuarios/user_form.html"
    success_url = reverse_lazy("user-list")
    success_message = 'Usuário "%(username)s" atualizado com sucesso.'
    extra_context = {
        "title": "Gerenciar Usuário",
        "subtitle": "Altere os dados cadastrais e as permissões de grupos do usuário.",
        "botao": "Salvar Alterações",
    }


# ─── Meu perfil (qualquer usuário logado, só os próprios dados) ───────────────

class MyProfileView(BaseLoginMixin, SuccessMessageMixin, UpdateView):
    form_class = MyProfileForm
    template_name = "usuarios/my_profile.html"
    success_url = reverse_lazy("my-profile")
    success_message = "Seus dados foram atualizados."

    def get_object(self, queryset=None):
        return self.request.user


class MyPasswordChangeView(BaseLoginMixin, SuccessMessageMixin, PasswordChangeView):
    template_name = "usuarios/password_change.html"
    success_url = reverse_lazy("my-profile")
    success_message = "Sua senha foi alterada."


# ─── Cadastro Público de Usuários (Sign Up) ───────────────────────────────────

class UserRegisterView(FormErrorMessagesMixin, CreateView):
    model = User
    form_class = UserRegisterForm
    template_name = "usuarios/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Cadastro realizado com sucesso! Faça login para continuar.")
        return response
