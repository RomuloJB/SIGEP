---
name: datatables-listagens
description: Use sempre que for criar ou editar um template de listagem (tabela que percorre registros de uma ListView/FilterView) deste projeto Django — aplica DataTables com busca e ordenação, data-sort em moeda/data/números e coluna de ações sem ordenação.
---

# Antes de mexer em qualquer template

Confira se a base já está instalada (hoje já está; só recrie se tiver sumido):

1. No `website/templates/website/model.html` (template base do projeto):
   - CSS no `<head>`: `https://cdn.datatables.net/2.1.8/css/dataTables.bootstrap5.min.css`
   - JS depois do `bootstrap.bundle.min.js` e FORA do `{% block scripts %}` (para
     templates que sobrescrevem o bloco não perderem o DataTables), nesta ordem:
     `https://code.jquery.com/jquery-3.7.1.min.js`,
     `https://cdn.datatables.net/2.1.8/js/dataTables.min.js`,
     `https://cdn.datatables.net/2.1.8/js/dataTables.bootstrap5.min.js` e
     `{% static 'js/datatables-init.js' %}`.
   - jQuery aparece UMA única vez. Não carregue de novo em outro template.
2. `static/js/datatables-init.js` inicializa toda `table.table-datatable` com
   `paging: false`, `info: false`, `lengthChange: false`, `order: []` e o idioma
   `https://cdn.datatables.net/plug-ins/2.1.8/i18n/pt-BR.json`.
3. O dashboard (`#datatablesSimple`) usa Simple-DataTables, outra biblioteca.
   Não misture: tabelas de listagem usam só `table-datatable`.

# Padrão de toda tabela de listagem

1. A tabela é sempre
   `<table class="table table-striped table-hover align-middle mb-0 table-datatable">`
   com `<thead class="table-light">`, dentro de `.table-responsive` no `.list-card`.
2. Nunca chame `.DataTable(...)` dentro de um template. A única inicialização é a
   do `datatables-init.js`.
3. Nunca ligue a paginação do DataTables. A paginação continua sendo do Django:
   `{% include 'cadastros/paginacao.html' %}` logo depois do `.table-responsive`
   (ver skill `django-filter-listagens`).
4. O projeto roda com `LANGUAGE_CODE = 'pt-br'` e `USE_THOUSAND_SEPARATOR = True`,
   então números saem formatados (`1.250,00`, `1.024`). Toda coluna numérica ou de
   data tem `data-sort` com o valor cru:
   - moeda: `<td data-sort="{{ obj.valor|stringformat:'.2f' }}">R$ {{ obj.valor|floatformat:2 }}</td>`
   - inteiros (ID, estoque, quantidade): `data-sort="{{ obj.campo|stringformat:'d' }}"`
   - `DateField`: `<td data-sort="{{ obj.campo|date:'Y-m-d' }}">{{ obj.campo|date:'d/m/Y' }}</td>`
   - `DateTimeField`: `<td data-sort="{{ obj.campo|date:'Y-m-d H:i' }}">{{ obj.campo|date:'d/m/Y H:i' }}</td>`
   - coluna de texto composto (ex.: "Pedido #12 - Cliente"): `data-sort` com o número.
5. Dentro de `data-sort="..."`, o argumento do filtro usa aspas simples.
6. Coluna de ações (menu Detalhes/Editar/Excluir) e qualquer coluna sem valor para
   ordenar: `<th data-orderable="false" data-searchable="false">Ações</th>`.
7. Lista vazia: nunca use `{% empty %}` com uma linha `<td colspan="...">` no
   `<tbody>` de uma `table-datatable` (quebra o DataTables). Deixe o `<tbody>` vazio;
   o DataTables mostra "Nenhum registro encontrado" em português.
8. Todo `<tr>` do `<tbody>` tem exatamente uma `<td>` por `<th>` do cabeçalho, sem
   `colspan` nem `rowspan`, e o `<thead>` tem uma única linha.
9. Cabeçalhos em português, com o nome que o usuário entende.

# Conferência antes de terminar

1. A busca aparece como "Pesquisar" e a página abre na ordem da view.
2. Ordenar uma coluna de moeda põe `R$ 89,90` antes de `R$ 15.000,00`.
3. A coluna "Ações" não tem setinha de ordenação.
4. Lista sem registros mostra "Nenhum registro encontrado", sem alerta "DataTables warning".
5. Só a paginação do Django aparece no rodapé.
