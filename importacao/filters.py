import django_filters

from .importadores import tipos_disponiveis
from .models import Importacao


class ImportacaoFilter(django_filters.FilterSet):
    situacao = django_filters.ChoiceFilter(choices=Importacao.Situacao.choices, label="Situação")
    tipo = django_filters.ChoiceFilter(choices=tipos_disponiveis, label="Tipo de documento")
    criado_em = django_filters.DateFromToRangeFilter(
        field_name="criado_em",
        label="Período",
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )

    class Meta:
        model = Importacao
        fields = []
