import django_filters
from django.utils import timezone

from .models import LimiteTelegram, MensagemTelegram


class MensagemTelegramFilter(django_filters.FilterSet):
    # Pode haver muitos usuários: busca pelo texto em vez de um <select>
    usuario = django_filters.CharFilter(field_name="usuario__username", lookup_expr="icontains", label="Usuário contém")
    direcao = django_filters.ChoiceFilter(choices=MensagemTelegram.Direcao.choices, label="Direção")
    situacao = django_filters.ChoiceFilter(choices=MensagemTelegram.Situacao.choices, label="Situação")
    criado_em = django_filters.DateFromToRangeFilter(
        field_name="criado_em",
        label="Período",
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"}),
    )

    class Meta:
        model = MensagemTelegram
        fields = []


class RemetenteTelegramFilter(django_filters.FilterSet):
    usuario = django_filters.CharFilter(field_name="usuario_site", lookup_expr="icontains", label="Usuário contém")
    bloqueio = django_filters.ChoiceFilter(
        choices=(("bloqueado", "Bloqueado"), ("livre", "Livre")), method="filtrar_bloqueio", label="Situação",
    )

    class Meta:
        model = LimiteTelegram
        fields = []

    def filtrar_bloqueio(self, queryset, name, value):
        bloqueados = {"bloqueado_ate__gt": timezone.now()}
        return queryset.filter(**bloqueados) if value == "bloqueado" else queryset.exclude(**bloqueados)
