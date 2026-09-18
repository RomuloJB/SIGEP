from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .masks import (
    CNPJ_DIGITS, CNPJ_FORMAT, CPF_DIGITS, CPF_FORMAT, PHONE_DIGITS, PHONE_FORMAT,
    format_cnpj, format_cpf, format_cpf_cnpj, format_phone, only_digits,
)
from .models import Client, Company, User_Profile


class MaskedDigitsField(forms.CharField):
    """
    Base para campos com máscara: o input exibe o valor formatado (máscara
    aplicada pelo static/js/masks.js e por prepare_value) e o banco recebe só
    os dígitos. Subclasses definem o nome da máscara (data-mask), os tamanhos
    aceitos, o pattern do navegador e o formatador de exibição.
    """
    mask = ""                 # valor de data-mask lido pelo masks.js
    allowed_lengths = ()      # quantidades de dígitos aceitas
    max_formatted_length = 0  # vira o maxlength do input
    pattern = ""              # validação no navegador
    placeholder = ""
    invalid_message = ""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", self.max_formatted_length)
        super().__init__(**kwargs)
        self.error_messages["invalid"] = self.invalid_message

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.update({
            "data-mask": self.mask,
            "inputmode": "numeric",
            "placeholder": self.placeholder,
            "pattern": self.pattern,
            # form-validation.js usa o title como mensagem de patternMismatch
            "title": self.invalid_message,
        })
        return attrs

    def format(self, value):
        raise NotImplementedError

    def to_python(self, value):
        value = super().to_python(value)
        return only_digits(value) if value else value

    def validate(self, value):
        super().validate(value)
        if value and len(value) not in self.allowed_lengths:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def prepare_value(self, value):
        return self.format(value)


class PhoneField(MaskedDigitsField):
    """Celular (NN) NNNNN-NNNN — compatível com User_Profile.phone (max_length=11)."""
    mask = "phone"
    allowed_lengths = (PHONE_DIGITS,)
    max_formatted_length = len(PHONE_FORMAT)
    pattern = r"\(\d{2}\) \d{5}-\d{4}"
    placeholder = "(41) 99999-9999"
    invalid_message = f"Informe o telefone no formato {PHONE_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Celular com DDD. Formato: {PHONE_FORMAT}")
        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.update({"inputmode": "tel", "autocomplete": "tel"})
        return attrs

    def format(self, value):
        return format_phone(value)


class CPFField(MaskedDigitsField):
    """CPF 000.000.000-00 — grava 11 dígitos (User_Profile.cpf tem max_length=14)."""
    mask = "cpf"
    allowed_lengths = (CPF_DIGITS,)
    max_formatted_length = len(CPF_FORMAT)
    pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    placeholder = CPF_FORMAT
    invalid_message = f"Informe o CPF no formato {CPF_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CPF_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cpf(value)


class CNPJField(MaskedDigitsField):
    """CNPJ 00.000.000/0000-00 — grava 14 dígitos (Company.cnpj tem max_length=18)."""
    mask = "cnpj"
    allowed_lengths = (CNPJ_DIGITS,)
    max_formatted_length = len(CNPJ_FORMAT)
    pattern = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
    placeholder = CNPJ_FORMAT
    invalid_message = f"Informe o CNPJ no formato {CNPJ_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CNPJ_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cnpj(value)


class CPFCNPJField(MaskedDigitsField):
    """CPF ou CNPJ, escolhido pela quantidade de dígitos (11 ou 14) — Client.cnpj_cpf."""
    mask = "cpf-cnpj"
    allowed_lengths = (CPF_DIGITS, CNPJ_DIGITS)
    max_formatted_length = len(CNPJ_FORMAT)
    pattern = r"(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
    placeholder = f"{CPF_FORMAT} ou {CNPJ_FORMAT}"
    invalid_message = f"Informe um CPF ({CPF_FORMAT}) ou CNPJ ({CNPJ_FORMAT})."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CNPJ_FORMAT} ou {CPF_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cpf_cnpj(value)


class UserProfileForm(forms.ModelForm):
    phone = PhoneField(label="Telefone")
    cpf = CPFField(label="CPF")

    class Meta:
        model = User_Profile
        fields = ["name", "phone", "cpf"]


class ClientForm(forms.ModelForm):
    cnpj_cpf = CPFCNPJField(label="CNPJ/CPF")

    class Meta:
        model = Client
        fields = ["name", "cnpj_cpf", "address", "city", "uf"]


class UserSearchMultipleField(forms.ModelMultipleChoiceField):
    """
    Seleção múltipla de usuários como dropdown com busca e "chips" removíveis
    (Tom Select, inicializado pelo static/js/select-search.js via data-tom-select).
    Escala melhor que um checkbox por usuário quando a base cresce.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", User.objects.order_by("first_name", "last_name", "username"))
        kwargs.setdefault("widget", forms.SelectMultiple(attrs={
            "data-tom-select": "",
            "data-placeholder": "Busque por nome ou usuário…",
        }))
        super().__init__(**kwargs)

    def label_from_instance(self, user):
        # Nome completo + usuário, para a busca encontrar por qualquer um dos dois
        full_name = user.get_full_name()
        return f"{full_name} ({user.username})" if full_name else user.username


class CompanyForm(forms.ModelForm):
    cnpj = CNPJField(label="CNPJ")
    manager = UserSearchMultipleField(label="Gerentes")
    sales_rep = UserSearchMultipleField(required=False, label="Representantes")

    class Meta:
        model = Company
        fields = ["name", "description", "cnpj", "manager", "sales_rep"]
