import re

from django import forms
from django.core.exceptions import ValidationError

from .models import User_Profile

PHONE_DIGITS = 11
PHONE_FORMAT = "(NN) NNNNN-NNNN"


def only_digits(value):
    return re.sub(r"\D", "", str(value or ""))


def format_phone(value):
    """'41999999999' -> '(41) 99999-9999'. Valores fora do padrão voltam como estão."""
    digits = only_digits(value)
    if len(digits) != PHONE_DIGITS:
        return value
    return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"


class PhoneField(forms.CharField):
    """
    Celular com máscara (NN) NNNNN-NNNN. O input exibe o valor formatado
    (máscara aplicada pelo static/js/masks.js) e o banco recebe só os 11 dígitos,
    compatível com User_Profile.phone (max_length=11).
    """
    default_error_messages = {
        "invalid": f"Informe o telefone no formato {PHONE_FORMAT}.",
    }

    def __init__(self, **kwargs):
        # 15 = tamanho do valor com máscara; vira o maxlength do input
        kwargs.setdefault("max_length", len(PHONE_FORMAT))
        kwargs.setdefault("help_text", f"Celular com DDD. Formato: {PHONE_FORMAT}")
        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.update({
            "data-mask": "phone",
            "inputmode": "tel",
            "autocomplete": "tel",
            "placeholder": "(41) 99999-9999",
            # validação no navegador (form-validation.js usa o title como mensagem)
            "pattern": r"\(\d{2}\) \d{5}-\d{4}",
            "title": self.default_error_messages["invalid"],
        })
        return attrs

    def to_python(self, value):
        value = super().to_python(value)
        return only_digits(value) if value else value

    def validate(self, value):
        super().validate(value)
        if value and len(value) != PHONE_DIGITS:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def prepare_value(self, value):
        return format_phone(value)


class UserProfileForm(forms.ModelForm):
    phone = PhoneField(label="Telefone")

    class Meta:
        model = User_Profile
        fields = ["name", "phone", "cpf"]
