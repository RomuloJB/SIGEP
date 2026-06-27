from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from cadastros.models import Company, User_Profile

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


# ─── Gerenciamento de Usuários (Apenas Superuser) ─────────────────────────────
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import UpdateView

class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class UserManageForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos / Permissões"
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active", "is_superuser"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona classes CSS do Bootstrap
        for field_name, field in self.fields.items():
            if field_name != 'groups':
                field.widget.attrs.update({'class': 'form-control'})
        
        if self.instance and self.instance.pk:
            self.fields['groups'].initial = self.instance.groups.all()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.groups.set(self.cleaned_data['groups'])
        return user


class UserListView(SuperuserRequiredMixin, ListView):
    model = User
    template_name = "usuarios/user_list.html"
    context_object_name = "users"
    paginate_by = 10


class UserUpdateView(SuperuserRequiredMixin, UpdateView):
    model = User
    form_class = UserManageForm
    template_name = "usuarios/user_form.html"
    success_url = reverse_lazy("user-list")
    extra_context = {"title": "Gerenciar Usuário", "botao": "Salvar Alterações"}


# ─── Cadastro Público de Usuários (Sign Up) ───────────────────────────────────

class UserRegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Senha",
        required=True
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmar Senha",
        required=True
    )
    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    # Campos do perfil
    name = forms.CharField(
        max_length=255,
        required=True,
        label="Nome completo",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        max_length=11,
        required=True,
        label="Telefone",
        help_text="Apenas números, com DDD. Exemplo: 41999999999",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    cpf = forms.CharField(
        max_length=14,
        required=True,
        label="CPF",
        help_text="Formato: 000.000.000-00",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona classes do bootstrap aos campos restantes
        for field_name, field in self.fields.items():
            if field_name not in ['password', 'confirm_password', 'email', 'name', 'phone', 'cpf']:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este e-mail já está em uso por outro usuário.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "As senhas não coincidem.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            User_Profile.objects.update_or_create(
                user=user,
                defaults={
                    'name': self.cleaned_data['name'],
                    'phone': self.cleaned_data['phone'],
                    'cpf': self.cleaned_data['cpf']
                }
            )
        return user


class UserRegisterView(CreateView):
    model = User
    form_class = UserRegisterForm
    template_name = "usuarios/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Cadastro realizado com sucesso! Faça login para continuar.")
        return response

