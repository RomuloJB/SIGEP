---
name: importacao-documentos
description: Use sempre que for criar ou alterar um importador de documento neste projeto Django (foto ou PDF lido pela IA que vira um rascunho e, confirmado, um registro), mexer no esquema Pydantic, nas instruções, no contexto ou na versão do prompt de uma leitura, ou acrescentar um campo editável ou um botão no cartão da importação no bot do Telegram. O contrato fica em importacao/importadores.py e cada app escreve o seu importador em <app>/importacao.py.
---

# Como a importação funciona

Foto ou PDF (site em `/importacao/nova/` ou bot) → `importacao/services.py` (`iniciar_importacao`,
`processar_importacao`, que chama a IA) → `importador.normalizar()` grava o rascunho em
`Importacao.dados` → a pessoa corrige (bot: `ajustar()`; site: tela Revisar com o `form()`) →
`confirmar_importacao` → `importador.confirmar()` cria o registro.

**Exemplo de referência:** `cadastros/importacao.py` (`ImportadorPedido`), com os testes em
`cadastros/tests/test_importacao.py`. Copie a estrutura dele.

# 1. Importador novo

Crie `<app>/importacao.py` com uma classe que herda `importacao.importadores.Importador` e leva
`@registrar`. O import no `ready()` já existe: `importacao/apps.py` chama
`autodiscover_modules("importacao")`, então basta o arquivo ter esse nome. O `@registrar` recusa
na hora quem não define `tipo`, `nome`, `esquema`, `instrucoes` e `versao_prompt`, ou cujas
instruções não terminam com `REGRA_DE_SEGURANCA`.

| Atributo / método | O que faz |
|---|---|
| `tipo`, `nome` | `"app.entidade"` e o nome que a pessoa vê ("Pedido de venda") |
| `esquema`, `esquema_sem_itens` | Pydantic que a IA devolve; o segundo (opcional) é a releitura sem itens quando a resposta corta (`MAX_TOKENS`). Só defina se o registro faz sentido sem itens |
| `instrucoes`, `versao_prompt` | texto da leitura e a versão `"AAAA-MM.N"` |
| `form_class` | o form do app, para a tela Revisar |
| `conferir_escopo(usuario, escopo)` | `""` se o escopo vale; senão, a mensagem de recusa. O services chama ao abrir, ler, corrigir e confirmar |
| `contexto(usuario, escopo)` | o texto com as listas do banco que a IA precisa (ids e nomes) |
| `normalizar(extracao, usuario, escopo)` | leitura → `(dados, avisos)`; documento de outro tipo: `raise NaoReconhecido(motivo)` |
| `campos()` | até 6 `Campo` que o bot deixa corrigir |
| `resumo(dados)` | `[(rótulo, texto)]` do cartão do bot e das telas do site |
| `ajustar(dados, codigo, valor, usuario, escopo)` | aplica uma correção → `(dados, mensagem)`, ou `raise AjusteInvalido(msg)` |
| `dados_para_form(dados)` / `form(usuario, escopo, data, initial)` | o rascunho no formato do form e o form montado (o `initial` chega também no POST) |
| `confirmar(dados, usuario, escopo, dados_form=None)` | cria o registro e o devolve, ou `raise ImportacaoInvalida(erros, form)` |

**Escopo** é o que o canal sabia ao abrir a importação, guardado em `Importacao.escopo`. No
pedido, ele é `{"empresa": id}`. No site, ele vem da sessão pelas chaves de
`settings.IMPORTACAO_ESCOPO_DA_SESSAO`; no bot, de `telegram.services.escopo_da_importacao`. O
importador confere a cada passo se a pessoa ainda está na empresa (`_empresa()` no exemplo).

# 2. Esquema e instruções

- **Reconhecimento:** `documento_reconhecido` e `motivo_nao_reconhecido` sempre. No
  `normalizar`, um documento não reconhecido vira `NaoReconhecido`.
- **Ids:** os campos `*_id` aceitam só ids das listas do contexto (até `LIMITE_LISTA = 200`). O
  `normalizar` confere se o id estava na lista enviada; fora dela, vira `None` com aviso. O que
  dá para casar no Python (CNPJ/CPF pelos dígitos, SKU) vale mais que a sugestão da IA.
- **Valores e datas:** chegam como `str | None` e são convertidos no `normalizar`. O que estiver
  ilegível fica vazio, com um aviso quando a pessoa precisa agir. Choices fixos (ex.:
  `PaymentMethod`) viram `Literal`.
- **Confiança:** `Literal["alta", "media", "baixa"]` nos 2 ou 3 campos críticos. Média ou baixa
  vira aviso.
- **Avisos da IA:** uma lista curta, cortada no `normalizar` (5 frases de até 200 caracteres).
- **Instruções:** em português, numeradas, com exemplos do domínio. Incluem "Use SOMENTE ids da
  lista; se nenhum servir, null" e "Nunca invente data, valor...", e terminam com
  `REGRA_DE_SEGURANCA`. Não repita o esquema no texto.
- **Mudou instruções ou esquema? Suba a `versao_prompt`.** Ela vai para a auditoria e separa as
  leituras: o services reaproveita uma leitura só com o mesmo arquivo, observação, prompt e escopo.
- **Contexto:** só o necessário, e só do escopo. Nada de CPF/CNPJ, e-mail, telefone, preço,
  estoque ou dados de outro usuário ou de outra empresa.

# 3. Confirmar

- **Validar:** use o form do app, o da tela de cadastro ou uma subclasse dele (ex.:
  `PedidoImportadoForm` em `cadastros/forms.py`). Use `dados_form` quando vier do site e
  `dados_para_form(dados)` quando vier do bot.
- **Criar:** pelo `services.py` do app (ex.: `cadastros/services.py`: `conferir_itens`,
  `salvar_pedido`, `criar_cliente`). Nunca use `Model.objects.create()` no importador. Se a
  criação estiver numa view, extraia para o service e faça a view usar a mesma função.
- **Erros:** as chaves de `ImportacaoInvalida.erros` são os códigos dos `campos()`, para o bot
  apontar o botão ✏️ certo (veja `_recusa()` no exemplo). O resto vai em `"__all__"`, e o bot
  manda corrigir em "🌐 Editar no site".
- **Transação:** o `confirmar` roda dentro do `transaction.atomic` de `confirmar_importacao`. Uma
  exceção desfaz tudo, inclusive a relacionada criada. Efeitos externos, como o e-mail, ficam em
  `transaction.on_commit`.
- **Isolamento:** `importacao/` nunca importa um app de domínio (`IsolamentoTestCase` em
  `importacao/tests/test_contrato.py`). No bot, a importação (`telegram/importacoes.py`, o cartão
  `telas.desenhar` e as ações em `telegram/acoes.py`) só usa `importacao/services.py`, o
  `resumo()` e os `campos()`. Nem o bot nem o importacao têm regra de negócio do domínio.

# 4. Campo editável ou botão novo

- **O campo:** `Campo(codigo, rotulo, tipo, opcoes=None, obrigatorio=False)`.
  - O código tem até 6 caracteres (`CODIGO_MAX`), e o cartão tem no máximo 6 campos.
  - O tipo é um destes: `texto`, `valor`, `data`, `inteiro` ou `escolha`.
  - No tipo `escolha`, `opcoes(usuario, escopo)` devolve `[(id, nome)]`, já filtrado pelo escopo.
- **Tratamento em `ajustar()`:**
  - O valor chega convertido por `telegram/entradas.py` (`ENTRADAS_DO_CAMPO` em
    `telegram/conversa.py`): `str`, `Decimal`, `date` ou `int` (a partir de 1).
  - No tipo `escolha`, chega o id de uma opção que `acoes._escolher_opcao` já conferiu.
  - Para recusar, levante `AjusteInvalido`.
  - Guarde no `dados` só o que é JSON: `Decimal` vira `str` e `date` vira `isoformat()`.
- **Callback de até 64 bytes** (`LIMITE_CALLBACK_BYTES` em `telegram/cliente.py`):
  - As opções viram `io:<importação>:<código>:<id da opção>`, então use ids curtos e sem `:`.
  - Os códigos de botão em uso são `ok`, `dc`, `it`, `tn`, `ic`, `il`, `io`, `iv`, `ab` e `pd`.
  - Um botão novo precisa de um código livre, da ação em `telegram/acoes.py` e de um teste.
- **Texto no cartão:** todo texto da pessoa ou do documento passa por
  `html.escape(texto, quote=False)`. O `telas.desenhar` já escapa o resumo e os avisos; o que você
  montar à mão no bot, escape também.
- **Chamadas ao Telegram:** sempre por `telegram/cliente.py`.

# Checklist antes de terminar

- [ ] Testes do importador sem IA: chame `normalizar` e `confirmar` com uma instância do esquema
      montada à mão. Cubra estes casos:
      - documento completo;
      - id fora da lista;
      - data ilegível;
      - documento não reconhecido;
      - relacionada reaproveitada;
      - escopo inválido;
      - contexto sem dado sensível (`assertNotIn`).
- [ ] Fluxo com a IA simulada:
      `mock.patch("importacao.services.chamar_ia", return_value=mock.Mock(dados=<instância do esquema>))`
      e o registro com `mock.patch.dict(REGISTRO, {...}, clear=True)`. O bot usa o cliente falso
      (`testes/telegram/base.py`, `BotTestCase`, `self.cliente.mensagens`), como em
      `testes/telegram/test_importacao.py`. Nada de internet nem de tokens.
- [ ] `.venv\Scripts\python.exe manage.py test cadastros importacao testes --keepdb`. O banco de
      teste fica no Neon; se a conexão cair, rode de novo só a classe que falhou.
- [ ] Mudou model? `makemigrations`, e quem aplica no Neon é o mantenedor.
- [ ] Teste com documentos reais pelo bot. Depois, em "Requisições de IA" (`/ia/requisicoes/`),
      confira:
      - a finalidade `importacao_ler` e a origem (`telegram` ou `site`);
      - a referência, que é a importação;
      - a `versao_prompt`, os tokens e o custo.
- [ ] A leitura passa sempre por `ia.chamada.chamar_ia`, nunca por `google-genai` direto. Siga a
      skill `app-ia`.
