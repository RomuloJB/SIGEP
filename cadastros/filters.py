import django_filters

from .masks import only_digits
from .models import Company, Client, User_Profile, Order, Product, ProductOrder, MeasureUnit, PaymentMethod


# Intervalo de datas: dois campos "de" e "até", do tipo date do HTML
def created_at_range():
    return django_filters.DateFromToRangeFilter(
        field_name='created_at',
        label='Cadastrado entre',
        widget=django_filters.widgets.RangeWidget(attrs={'type': 'date'}),
    )


class DigitsFilterMixin:
    """
    CPF, CNPJ e telefone são gravados só com dígitos. Remove a máscara do que
    o usuário digitou antes de comparar, para "123.456" encontrar "123456...".
    """
    def filter_digits(self, queryset, name, value):
        digits = only_digits(value)
        if not digits:
            return queryset
        return queryset.filter(**{f'{name}__icontains': digits})


class CompanyFilter(DigitsFilterMixin, django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label='Nome contém')
    cnpj = django_filters.CharFilter(method='filter_digits', label='CNPJ contém')
    created_at = created_at_range()

    class Meta:
        model = Company
        fields = []


class ClientFilter(DigitsFilterMixin, django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label='Nome contém')
    cnpj_cpf = django_filters.CharFilter(method='filter_digits', label='CNPJ/CPF contém')
    city = django_filters.CharFilter(lookup_expr='icontains', label='Cidade contém')
    uf = django_filters.CharFilter(lookup_expr='iexact', label='UF')
    created_at = created_at_range()

    class Meta:
        model = Client
        fields = []


class UserProfileFilter(DigitsFilterMixin, django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label='Nome contém')
    phone = django_filters.CharFilter(method='filter_digits', label='Telefone contém')
    cpf = django_filters.CharFilter(method='filter_digits', label='CPF contém')

    class Meta:
        model = User_Profile
        fields = []


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label='Nome contém')
    sku = django_filters.CharFilter(lookup_expr='icontains', label='SKU contém')
    color = django_filters.CharFilter(lookup_expr='icontains', label='Cor contém')
    measure_unit = django_filters.ChoiceFilter(choices=MeasureUnit.choices, label='Unidade de medida')
    unit_value_min = django_filters.NumberFilter(field_name='unit_value', lookup_expr='gte', label='Valor unitário a partir de')
    unit_value_max = django_filters.NumberFilter(field_name='unit_value', lookup_expr='lte', label='Valor unitário até')
    stock_min = django_filters.NumberFilter(field_name='stock', lookup_expr='gte', label='Estoque a partir de')
    stock_max = django_filters.NumberFilter(field_name='stock', lookup_expr='lte', label='Estoque até')

    class Meta:
        model = Product
        fields = []


class OrderFilter(django_filters.FilterSet):
    # Uma empresa pode ter muitos clientes: busca pelo texto em vez de um <select>
    client_name = django_filters.CharFilter(field_name='client__name', lookup_expr='icontains', label='Cliente contém')
    type = django_filters.ChoiceFilter(choices=Order.TYPES, label='Tipo')
    payment_method = django_filters.ChoiceFilter(choices=PaymentMethod.choices, label='Forma de pagamento')
    total_value_min = django_filters.NumberFilter(field_name='total_value', lookup_expr='gte', label='Valor total a partir de')
    total_value_max = django_filters.NumberFilter(field_name='total_value', lookup_expr='lte', label='Valor total até')
    created_at = created_at_range()

    class Meta:
        model = Order
        fields = []


class ProductOrderFilter(django_filters.FilterSet):
    order = django_filters.NumberFilter(field_name='order__id', label='Pedido nº')
    client_name = django_filters.CharFilter(field_name='order__client__name', lookup_expr='icontains', label='Cliente contém')
    product_name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains', label='Produto contém')
    total_value_min = django_filters.NumberFilter(field_name='total_value', lookup_expr='gte', label='Valor total a partir de')
    total_value_max = django_filters.NumberFilter(field_name='total_value', lookup_expr='lte', label='Valor total até')

    class Meta:
        model = ProductOrder
        fields = []
