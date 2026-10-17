import django_filters
from django.contrib.auth.models import User
from django.db.models import Q

from .models import RequisicaoIA


class RequisicaoIAFilter(django_filters.FilterSet):
    # Pode haver muitos usuários: busca pelo texto em vez de um <select>
    usuario = django_filters.CharFilter(field_name="usuario__username", lookup_expr="icontains", label="Usuário contém")
    situacao = django_filters.ChoiceFilter(choices=RequisicaoIA.Situacao.choices, label="Situação")
    finalidade = django_filters.CharFilter(lookup_expr="icontains", label="Finalidade contém")
    origem = django_filters.ChoiceFilter(choices=RequisicaoIA.Origem.choices, label="Origem")
    criado_em = django_filters.DateFromToRangeFilter(
        field_name="criado_em",
        label="Período",
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )

    class Meta:
        model = RequisicaoIA
        fields = []


class UsuarioIAFilter(django_filters.FilterSet):
    nome = django_filters.CharFilter(method="filtrar_nome", label="Usuário ou nome contém")
    ia = django_filters.ChoiceFilter(
        choices=(("ligada", "Ligada"), ("desligada", "Desligada")), method="filtrar_ia", label="IA",
    )

    class Meta:
        model = User
        fields = []

    def filtrar_nome(self, queryset, name, value):
        return queryset.filter(
            Q(username__icontains=value) | Q(first_name__icontains=value) | Q(last_name__icontains=value)
        )

    def filtrar_ia(self, queryset, name, value):
        # Sem ConfiguracaoIAUsuario a IA está ligada (padrão)
        desligada = Q(configuracao_ia__ia_habilitada=False)
        return queryset.filter(desligada) if value == "desligada" else queryset.exclude(desligada)
