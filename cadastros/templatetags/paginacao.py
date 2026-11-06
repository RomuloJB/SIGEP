from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_pagina(context, numero):
    """
    Link de uma página da listagem que mantém os filtros do django-filter.
    Parte da querystring atual (?name=re&uf=PR&page=1), troca só o page e devolve
    "?name=re&uf=PR&page=2". Campos com vários valores (ex.: ?uf=PR&uf=SC) são
    preservados, e o valor é escapado (urlencode).

    Uso: {% load paginacao %} ... <a href="{% url_pagina page_obj.next_page_number %}">
    """
    parametros = context["request"].GET.copy()
    parametros["page"] = numero
    return "?" + parametros.urlencode()
