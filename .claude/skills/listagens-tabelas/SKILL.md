---
name: listagens-tabelas
description: Use sempre que for criar ou editar um template de listagem (tabela de registros de uma ListView/FilterView) ou uma tabela com dados deste projeto Django — define a estrutura do card, a tabela com busca rápida e ordenação em JS puro (valores no formato brasileiro), o filtro no header e o dropdown de ações com ícones coloridos.
---

# Base visual

O visual vem de `static/css/sigep-ui.css` (carregado depois do `styles.css` no
`website/templates/website/model.html`). A busca e a ordenação vêm de
`static/js/tabela-lista.js`. Não existe DataTables, jQuery plugin nem biblioteca
de tabela: não adicione nenhuma.

# Estrutura de toda listagem

```django
<div class="page-header">
    <div>
        <h1 class="page-title"><i class="fas fa-box"></i> Produtos</h1>
        <p class="page-subtitle">Frase que explica o que a pessoa faz nesta tela.</p>
    </div>
    <div class="page-actions">
        <a class="btn btn-primary" href="{% url 'product-create' %}"><i class="fas fa-plus"></i> Novo produto</a>
    </div>
</div>

<div class="card list-card">
    <div class="card-header">
        <div class="card-heading">
            <h2 class="card-title"><i class="fas fa-list"></i> Lista de produtos</h2>
            <span class="card-meta">{{ page_obj.paginator.count }} registro{{ page_obj.paginator.count|pluralize }}</span>
        </div>
        <div class="card-tools">{% include 'cadastros/form-filter.html' %}</div>
    </div>
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0 table-lista"> ... </table>
    </div>
    {% include 'cadastros/paginacao.html' %}
</div>
```

1. Título à esquerda no `card-header`; à direita ficam as ferramentas (`card-tools`):
   o campo "Buscar nesta página…" (criado pelo JS, sempre o primeiro) e o filtro.
2. O filtro do django-filter é o botão de ícone claro do `form-filter.html`, dentro
   do `card-tools`. Quando o filtro vale para a página toda (ex.: relatório), use no
   `page-actions` com `rotulo="Filtros"`. Ver skill `django-filter-listagens`.
3. A tabela leva `table-lista`, sem `table-striped` e sem `table-light`.
4. A paginação continua sendo do Django (`cadastros/paginacao.html`). A busca e a
   ordenação só atuam nas linhas da página atual.
5. Título e subtítulo da página: o título é o nome da tela; o subtítulo diz, em uma
   frase, o que dá para fazer ali. Todo `h1` do `page-title` leva um ícone.

# Tabela

- Cabeçalhos em português; colunas numéricas e de moeda com `class="text-end"` no
  `th` e no `td`.
- Coluna de ações: `<th class="text-end" data-orderable="false" data-searchable="false">Ações</th>`.
  Toda coluna sem valor útil para ordenar usa `data-orderable="false"`; toda coluna
  que não deve entrar na busca usa `data-searchable="false"`.
- Ordenação: clicar no título ordena crescente, de novo decrescente, de novo volta
  à ordem original. O ícone mostra o estado. O JS lê o texto no formato brasileiro
  (`R$ 1.250,00`, `1.024`, `31/12/2026 14:30`, `11/2026`, `#12`), então não precisa
  de `data-sort` nesses casos. Use `data-sort` só quando o texto exibido não ordena
  bem (ex.: "Pedido #12 - Cliente" → `data-sort="12"`); nele valem números com ponto
  (`1234.50`) ou datas ISO (`2026-11-05 14:30`).
- Links dentro da tabela são cinza escuro (o CSS já faz); não use `text-primary`,
  `link-primary` nem `text-decoration-none` nos links da tabela.
- SKU: `<span class="sku">{{ p.sku }}</span>`. Status: `badge-soft-*`
  (ver `cadastros/pedido-status.html`). Nunca `badge bg-*`.
- Lista vazia: deixe o `<tbody>` vazio (o JS mostra "Nenhum registro encontrado").
  Em tabela de detalhe com `{% empty %}`, use uma `<td class="list-empty">`; o JS
  ignora essa linha.
- Tabelas de detalhe que listam registros (itens do pedido, pedidos do cliente)
  também levam `table-lista`.

# Menu de ações da linha

```django
<td class="text-nowrap text-end">
  <div class="dropdown">
    <button class="btn btn-ghost btn-icon btn-sm" type="button" data-bs-toggle="dropdown"
            data-bs-boundary="viewport" data-bs-strategy="fixed" aria-expanded="false"
            aria-label="Ações do cliente {{ client.name }}">
      <i class="fas fa-ellipsis-vertical"></i>
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
      <li><a class="dropdown-item" href="..."><i class="fas fa-eye icon-view"></i> Detalhes</a></li>
      <li><a class="dropdown-item" href="..."><i class="fas fa-pen-to-square icon-edit"></i> Editar</a></li>
      <li><a class="dropdown-item" href="..."><i class="fas fa-copy icon-duplicate"></i> Duplicar</a></li>
      <li><hr class="dropdown-divider"></li>
      <li>{% include 'cadastros/form-excluir.html' with ... classe="dropdown-item" %}</li>
    </ul>
  </div>
</td>
```

- O texto do item é sempre escuro; só o ícone muda de cor: `icon-view` (verde-acinzentado),
  `icon-edit` (azul), `icon-duplicate` (dourado), `icon-delete` (vermelho),
  `icon-approve` (verde). Excluir usa `classe="dropdown-item"` (sem `text-danger`;
  o ícone vermelho já vem do `form-excluir.html`).
- Ordem: Detalhes, Editar, Duplicar, divisor, Excluir.
- O corte do menu na última linha já é tratado pelo `tabela-lista.js`; não repita o
  script nos templates.

# Conferência antes de terminar

1. Campo de busca à direita do título; digitar esconde linhas e mostra "Nenhum
   registro encontrado" quando nada bate.
2. Ordenar valor em reais, data brasileira e ID numérico (`#10` depois de `#9`).
3. Coluna "Ações" sem botão de ordenação.
4. O menu de ações da última linha abre inteiro, sem ser cortado.
5. Em tela estreita o campo de busca ocupa a linha inteira do header.
