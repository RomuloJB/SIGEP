---
name: cards-kpi
description: Use sempre que for criar ou editar um card de indicador (KPI) ou padronizar a formatação de cards (Dashboard, relatórios, telas de detalhe) neste projeto Django — card KPI com fundo branco e ícone colorido via include, cabeçalho de card padrão e regras de cores.
---

# Card KPI

Sempre via include; não escreva o HTML do KPI à mão e não use `stat-card`
(removido):

```django
{% include 'website/componentes/kpi-card.html' with label="Total vendido" valor=total_vendas moeda=True icone="fa-sack-dollar" cor="primary" %}
```

- `label`: o que o número mede, em frase curta e sem caixa alta.
- `valor`: o número cru. Com `moeda=True` sai `R$ 1.250,00`; sem, sai como veio.
- `icone`: classe Font Awesome (`fa-*`), sempre presente.
- `cor`: `primary` (verde da marca, padrão), `info` (azul), `warning` (dourado),
  `danger` (vermelho), `neutral` (cinza). Só o bloco do ícone é colorido; o card
  é branco.
- `ajuda` (opcional): linha pequena abaixo do valor.
- Valores que não são `moeda` e precisam de prefixo (ex.: `US$`) podem ter o card
  escrito com as classes `card kpi-card kpi-info` > `card-body` > `kpi-icon` +
  `kpi-body` (`kpi-label`, `kpi-value`), igual ao include.

Layout: linha `row g-4 mb-4` com colunas iguais (`col-xl-3 col-md-6` para 4 cards,
`col-md-4` para 3). Associe cores ao significado, não à posição: dinheiro = primary,
quantidade = warning, tempo/ticket = info, erro = danger, pessoas = neutral.

# Padrão de todo card

Dashboard, relatórios, detalhes e formulários usam o mesmo `.card`:

```django
<div class="card">
  <div class="card-header">
    <h2 class="card-title"><i class="fas fa-chart-area"></i> Título do card</h2>
    <span class="card-meta">Informação secundária (opcional)</span>
  </div>
  <div class="card-body">...</div>
</div>
```

- Cabeçalho branco, título com ícone verde. Nunca fundo verde/gradiente, caixa alta
  ou texto branco no `card-header`.
- Tabela dentro do card: sem `card-body`, direto no `table-responsive` (ver skill
  `listagens-tabelas`). Detalhe chave/valor: `card-body p-0` + `table`.
- Texto auxiliar dentro do card: `page-subtitle` (cinza) em vez de `text-muted small`.
- Cards lado a lado: `h-100`. Espaço entre blocos: `mb-4`.
- O padding do card e das células de tabela já vem do `sigep-ui.css`; não ajuste
  com utilitários (`p-3`, `px-4`).
