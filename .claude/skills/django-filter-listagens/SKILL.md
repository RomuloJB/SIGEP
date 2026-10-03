---
name: django-filter-listagens
description: Use sempre que for criar, editar ou revisar filtros de busca em uma listagem (ListView/FilterView) deste projeto Django — segue o padrão django-filter com filters.py, PaginatedFilterView, form-filter.html e paginacao.html.
---

# Antes de mexer em qualquer listagem

Confira a base (já existe hoje; só recrie se tiver sumido):

1. `django-filter` está no `requirements.txt` e `'django_filters'` (underline, plural)
   está no `INSTALLED_APPS`.
2. Crispy Forms com Bootstrap 5 configurado (`crispy_forms`, `crispy_bootstrap5`,
   `CRISPY_ALLOWED_TEMPLATE_PACKS` e `CRISPY_TEMPLATE_PACK` = `'bootstrap5'`).
   Os ícones do projeto são **Font Awesome** (`fas fa-...`), carregado no
   `website/model.html` — não use Bootstrap Icons (`bi-...`), que não está carregado.
3. Existe UM `cadastros/templates/cadastros/form-filter.html` (formulário de filtros)
   e UM `cadastros/templates/cadastros/paginacao.html` (rodapé de paginação que
   repete todos os parâmetros da URL, exceto `page`). Nunca duplique esses trechos.

# O filtro (cadastros/filters.py)

1. Um `FilterSet` por model, chamado `<Model>Filter` (ex.: `ProductFilter`).
2. **Declare cada filtro** com `label` em português e deixe `Meta.fields = []`
   (os rótulos automáticos do `Meta.fields` saem como "nome contains", a partir do
   `verbose_name` em minúsculas).
   - texto (`CharField`, `TextField`): `CharFilter(lookup_expr='icontains', label='... contém')`
   - número e moeda: dois `NumberFilter` com `lookup_expr='gte'` / `'lte'`
     (`<campo>_min` / `<campo>_max`, rótulos "... a partir de" / "... até")
   - campos com `choices`: `ChoiceFilter(choices=..., label=...)`
3. CPF, CNPJ e telefone são gravados só com dígitos: use
   `CharFilter(method='filter_digits', ...)` com o `DigitsFilterMixin` (que reusa
   `masks.only_digits`), para a busca funcionar com ou sem máscara.
4. Chave estrangeira com muitas opções (clientes, produtos): busca por texto,
   `CharFilter(field_name='<relacao>__name', lookup_expr='icontains')`.
   Se usar `ModelChoiceFilter`, o `queryset` DEVE ser uma função do `request`
   restrita à empresa ativa
   (`lambda request: Modelo.objects.filter(company_id=request.session.get('active_company_id'))`),
   senão a lista suspensa mostra dados de outras empresas.
5. Datas (`created_at` é `DateTimeField`): use o helper `created_at_range()`
   (`DateFromToRangeFilter` + `RangeWidget(attrs={'type': 'date'})`). Se precisar de
   dois `DateFilter` separados, use `date__gte` / `date__lte`, nunca `gte`/`lte` puros.
6. Não crie filtro para `id` técnico, senha, `created_by` ou `company` (o escopo
   por empresa já é feito pelo `ActiveCompanyRequiredMixin`).

# A view (cadastros/views.py)

1. A listagem herda de `PaginatedFilterView` (FilterView + `?per_page=10|20|40`),
   mantendo os mixins de acesso (`GroupRequiredMixin`, `ActiveCompanyRequiredMixin`,
   `BaseLoginMixin`) ANTES dela, na mesma ordem.
2. Atributos obrigatórios: `model`, `template_name`, `ordering` (evita
   `UnorderedObjectListWarning`) e `filterset_class`.
3. `get_queryset` sempre parte de `super().get_queryset()` (é ali que entra o filtro
   por empresa ativa); o django-filter é aplicado por cima.
4. Se a tabela mostra atributos de relações (`obj.client.name`), use `select_related`.

# O template da lista

1. O `form-filter.html` é um botão "Filtros" com dropdown (badge com o número de
   filtros ativos, vindo de `active_filters` da `PaginatedFilterView`). Ele fica no
   cabeçalho, dentro de `<div class="list-actions">`, antes do botão "Novo":
   `{% include 'cadastros/form-filter.html' %}`. O estilo está em `styles.css`
   (`.filter-dropdown`), não no template.
2. Dentro do card, depois do `.table-responsive`: `{% include 'cadastros/paginacao.html' %}`.
3. Nunca copie o formulário de filtros ou a paginação para dentro do template.
4. A tabela continua percorrendo `<model>_list` / `object_list`.
5. As regras da tabela (classes, `data-sort`, coluna de ações, lista vazia) são as
   da skill `datatables-listagens`. Esta skill cuida do formulário de filtros, da
   view e da paginação.

# Conferência antes de terminar

1. Lista sem parâmetros mostra todos os registros da empresa ativa.
2. Parte de um texto encontra o registro; faixa de datas inclui o último dia.
3. Na página 2 (ou trocando "Itens por página") os filtros continuam na URL.
4. "Limpar" volta para a lista sem parâmetros.
5. `python manage.py check` sem erros.
