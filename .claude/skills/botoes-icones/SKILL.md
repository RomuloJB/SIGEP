---
name: botoes-icones
description: Use sempre que for criar ou editar um botão, link-botão ou ícone neste projeto Django — define os estilos de botão (sólido, contorno, suave, ícone), qual ícone Font Awesome usar em cada ação, a ordem dos botões e onde ficam nas telas de lista, detalhe e formulário.
---

# Regra geral

- Todo botão tem ícone Font Awesome (`fas fa-*`) antes do texto, mesmo os de
  formulário e modal. Botão só com ícone leva `aria-label` e `title`.
- Não use `me-1` no ícone: o `.btn` já tem `gap`.
- Estilos vêm do `static/css/sigep-ui.css`. Não use `btn-novo`, `btn-sm` solto para
  "caber" nem `btn-success` (hoje é igual ao `btn-primary`; use `btn-primary`).

# Estilos

| Uso | Classe |
|---|---|
| Ação principal da tela (Novo, Salvar, Enviar) — só uma por área | `btn btn-primary` |
| Ação secundária (Editar, Duplicar, Salvar em rascunho) | `btn btn-outline-primary` |
| Neutra (Voltar, Cancelar, Limpar) | `btn btn-outline-secondary` |
| Perigosa (Excluir, Rejeitar) | `btn btn-outline-danger` (`btn-danger` só no botão de confirmar) |
| Filtro e destaques de apoio | `btn btn-soft-primary` (fundo verde claro); variantes `btn-soft-neutral/info/warning/danger` |
| Só ícone (menu de ações da linha) | `btn btn-ghost btn-icon btn-sm` |
| Só ícone, destaque (filtro no card) | `btn btn-soft-primary btn-icon` |
| Link de texto discreto | `btn-link-muted` |

Evite `btn-warning`/`btn-info` sólidos: use as versões `soft` ou `outline`.

# Ícones por ação (use sempre o mesmo)

| Ação | Ícone | Ação | Ícone |
|---|---|---|---|
| Novo / Adicionar | `fa-plus` | Voltar | `fa-arrow-left` |
| Salvar | `fa-floppy-disk` | Cancelar / Limpar | `fa-xmark` |
| Editar | `fa-pen-to-square` | Excluir | `fa-trash` |
| Detalhes / Ver | `fa-eye` | Duplicar | `fa-copy` |
| Filtrar (abrir) | `fa-filter` | Aplicar filtro / Buscar | `fa-magnifying-glass` |
| Enviar | `fa-paper-plane` | Menu de ações | `fa-ellipsis-vertical` |
| Alterar senha | `fa-key` | Voltar ao padrão | `fa-rotate-left` |
| Ver todos / lista | `fa-list` | Ver pedido | `fa-file-invoice` |

Ícones de cabeçalho de página e de card: um por tela/seção, sempre o mesmo para a
mesma entidade (Empresas `fa-building`, Clientes `fa-users`, Produtos `fa-box`,
Pedidos `fa-cart-shopping`, Relatórios `fa-chart-line`, Dashboard `fa-gauge-high`).

# Onde ficam

- Lista: botão "Novo" no `page-actions` (direita do título). Filtro e busca no
  `card-header` da tabela (skill `listagens-tabelas`).
- Detalhe: `page-actions` com Voltar (`outline-secondary`), Editar
  (`outline-primary`), Duplicar (`outline-primary`) e Excluir (`outline-danger`,
  via `cadastros/form-excluir.html`, skill `bootbox-confirmacoes`).
- Formulário: botões só no fim do formulário, alinhados à direita
  (`.cadastros-actions` ou `.form-actions`), nunca repetidos no cabeçalho. Ordem:
  Cancelar, secundário, principal (ex.: Cancelar, Salvar em rascunho, Salvar e enviar).
- Botão que grava dados leva a classe `btnLoading` (o base mostra o estado de envio).
- Ícones coloridos só dentro de `dropdown-item` (`icon-view`, `icon-edit`,
  `icon-duplicate`, `icon-delete`, `icon-approve`); em botões o ícone herda a cor.
