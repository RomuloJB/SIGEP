---
name: bootbox-confirmacoes
description: Use sempre que for escrever um alert()/confirm()/prompt(), um aviso ao usuário em JavaScript ou um botão/link de exclusão (DeleteView) neste projeto Django — troca os diálogos nativos por Bootbox com título e aplica a confirmação de exclusão (simples ou digitando "excluir" nas exclusões perigosas).
---

# Antes de gerar qualquer diálogo

A base já está instalada (só recrie se tiver sumido):

1. `website/templates/website/model.html`, fora do `{% block scripts %}`, nesta ordem:
   jQuery 3.7.1 → `bootstrap.bundle.min.js` → `https://cdnjs.cloudflare.com/ajax/libs/bootbox.js/6.0.0/bootbox.min.js`
   → `{% static 'js/confirmar-exclusao.js' %}`. jQuery aparece UMA única vez.
2. Convenção de botões do projeto: confirmar exclusão `btn-danger`, cancelar
   `btn-outline-secondary` (a mesma de `form_delete.html`). Não invente outras.

# Instruções

1. Nunca gere `alert(...)`, `confirm(...)` ou `prompt(...)` nativos — use o Bootbox:
   - Aviso simples → `bootbox.alert({ title, message })`
   - Pergunta sim/não → `bootbox.confirm({ title, message, buttons, callback })`
   - Entrada de texto → `bootbox.prompt({ title, placeholder, callback })`
   - Operação demorada → `bootbox.dialog({ title, message: '<spinner-border do Bootstrap 5>', closeButton: false })`,
     sem `buttons`, fechado com `.modal('hide')` na referência retornada quando terminar.
2. Todo diálogo tem `title`. O rodapé só existe quando há `buttons`.
3. `message` é HTML: qualquer dado vindo do banco entra escapado (`textContent`), nunca concatenado cru.
4. Exclusão nunca é um link `<a href="...-delete">`. É sempre o include, que envia POST
   para a DeleteView depois da confirmação do Bootbox:
   ```django
   {% url 'client-delete' client.pk as url_excluir %}
   {% include 'cadastros/form-excluir.html' with url=url_excluir titulo="Excluir cliente" tipo="o cliente" nome=client.name classe="dropdown-item text-danger" %}
   ```
   - `titulo`: "Excluir <o que é>"; `tipo`: com artigo ("o cliente", "a empresa", "o pedido nº");
     `nome`: o registro citado na mensagem; `classe`: `dropdown-item text-danger` no menu de
     ações da listagem, `btn btn-outline-danger btn-novo` nas telas de detalhe.
   - Não escreva JS por template: `confirmar-exclusao.js` intercepta toda `form.form-excluir`.
5. Exclusão perigosa (empresa, perfil de gerente, ou algo que apague muitos dados em
   cascata) exige digitar "excluir", como no GitHub:
   - no include, `digitar=True` (o modal só libera "Sim, excluir" depois da palavra);
   - na view, `ConfirmacaoDigitadaMixin` antes dos outros mixins da DeleteView — o
     servidor confere a palavra de novo. Se só alguns registros forem perigosos,
     sobrescreva `exige_confirmacao_digitada()` (ex.: `UserProfileDelete` usa
     `self.object.is_manager`) e use `{% if %}` no template com a mesma regra.
6. Toda DeleteView começa com `ExclusaoProtegidaMixin`: registro preso por FK `PROTECT`
   não dá 500, volta para a página anterior com `messages.error` dizendo o que está
   vinculado. As mensagens do Django são exibidas como `bootbox.alert` por
   `static/js/mensagens.js` (incluído no `model.html` só quando há mensagens).
7. `cadastros/form_delete.html` continua sendo a página da DeleteView (fallback sem JS ou
   sem a CDN); ela já mostra o campo "excluir" quando o form da view o exige.
8. Nunca remova a confirmação de exclusão para "simplificar".

# Conferência antes de terminar

1. Clicar em "Excluir" abre o modal antes de qualquer requisição (aba Rede do navegador vazia).
2. Exclusão perigosa: o botão "Sim, excluir" fica desabilitado até digitar "excluir".
3. POST direto sem `confirmacao=excluir` numa view perigosa volta 200 com erro, sem excluir.
4. `grep -rn "alert(\|confirm(\|prompt(" static/js cadastros usuarios website` não acha diálogos nativos.
