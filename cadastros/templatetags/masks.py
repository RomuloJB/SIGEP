from django import template

from cadastros.masks import format_cnpj, format_cpf, format_cpf_cnpj, format_phone

register = template.Library()


@register.filter
def phone(value):
    """Telefone gravado como dígitos -> (NN) NNNNN-NNNN."""
    return format_phone(value)


@register.filter
def cpf(value):
    """CPF gravado como dígitos -> 000.000.000-00."""
    return format_cpf(value)


@register.filter
def cnpj(value):
    """CNPJ gravado como dígitos -> 00.000.000/0000-00."""
    return format_cnpj(value)


@register.filter
def cpf_cnpj(value):
    """CPF ou CNPJ, pela quantidade de dígitos (11 ou 14)."""
    return format_cpf_cnpj(value)
