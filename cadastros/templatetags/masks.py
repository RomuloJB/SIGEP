from django import template

from cadastros.forms import format_phone

register = template.Library()


@register.filter
def phone(value):
    """Exibe o telefone gravado como dígitos no formato (NN) NNNNN-NNNN."""
    return format_phone(value)
