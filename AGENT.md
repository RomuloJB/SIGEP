# AGENT.md — SIGEP (Sistema de Gestão de Pedidos)

Este arquivo orienta agentes de IA (Claude Code e similares) que forem trabalhar
neste repositório. Leia-o inteiro antes de propor ou aplicar qualquer mudança.

## 1. O que é o projeto

SIGEP é uma aplicação web para **gestão de pedidos comerciais** voltada a empresas
que operam com **representantes de vendas**. É um Trabalho de Conclusão de Curso
(TCC/NAES) do IFPR, em estágio **intermediário de desenvolvimento** — parte dos
requisitos já está implementada e funcional, parte ainda está pendente (ver Seção 8).

O sistema é **multiempresa (multi-tenant)**: uma única instância atende várias
empresas isoladamente. Cada empresa tem seus próprios clientes, produtos, pedidos
e usuários vinculados. Não há integração com ERPs externos, emissão de NF-e,
pagamentos online nem logística — isso está fora do escopo, de propósito.

## 2. Stack técnica

- **Linguagem/Framework:** Python + Django 5.2 (arquitetura MVT)
- **Banco de dados:** PostgreSQL, hospedado no Neon (`DATABASE_URL` via `.env`)
- **Frontend:** templates Django + Bootstrap 5 (tema baseado no template
  "SB Admin" / startbootstrap), jQuery/JS puro (sem SPA)
- **Bibliotecas Django relevantes:**
  - `django-crispy-forms` + `crispy-bootstrap5` — renderização de formulários
  - `django-braces` — mixins de views (`GroupRequiredMixin`, `LoginRequiredMixin`)
  - `django-autocomplete-light`, `django-filter`, `django-extensions` — instaladas,
    uso pontual
  - `django-debug-toolbar` — ativo em `DEBUG=True`
- **Deploy:** Google Cloud Platform (App Engine), via `app.yaml` e `gcloud app deploy`
- **Versionamento:** Git + GitHub

Ver `requirements.txt` para versões exatas antes de instalar/atualizar pacotes.

## 3. Estrutura de apps Django

```
naes2026/     → projeto Django (settings, urls raiz, wsgi/asgi)
website/      → landing page pública, dashboard (Index com gráficos), about/contact
usuarios/     → autenticação, seleção/ativação de empresa ativa, gestão de usuários
cadastros/    → núcleo do sistema: Company, Client, Product, Order, ProductOrder
sigep/        → app "casca", sem models/views ativos (histórico, ver Seção 9)
license/      → app "casca", models comentados (planejamento de licenciamento/SaaS,
                não implementado — ver Seção 9)
static/       → JS/CSS globais (masks.js, order-scripts.js, dashboard-charts.js…)
```

Cada app segue o padrão `models.py` / `forms.py` / `views.py` (CBVs genéricas) /
`urls.py` / `templates/<app>/`.

## 4. Modelo de dados (app `cadastros`)

- **`User_Profile`** — dados pessoais (nome, telefone, CPF) ligados 1:1 a `auth.User`.
- **`Company`** — empresa (tenant). `manager` e `sales_rep` são M2M para `auth.User`.
  Superusuários são sempre adicionados como `manager` de qualquer empresa criada/editada.
- **`Client`** — cliente de uma `Company` (FK `company`, `on_delete=PROTECT`).
- **`Product`** — produto de uma `Company`, com `stock` (estoque) e `unit_value`.
  `MeasureUnit` (UND/KIT/CX6/CX7/CX8) e SKU único por produto.
- **`Order`** — pedido de uma `Company` para um `Client`. Tipo `IN`/`OUT`,
  `payment_method` (choices `PaymentMethod`), `total_value` calculado no backend.
- **`ProductOrder`** — item de pedido (produto + quantidade + desconto + total),
  M:1 com `Order` e `Product`.
- **`BaseClass`** (abstrata) — `created_at`, `updated_at`, `created_by` (FK
  `auth.User`, `PROTECT`). Reutilizada por `Company`, `Client`, `Product`, `Order`.

CNPJ, CPF e telefone são armazenados **somente com dígitos** no banco; a máscara
de exibição/validação fica em `cadastros/masks.py` e nos campos customizados de
`cadastros/forms.py` (`PhoneField`, `CPFField`, `CNPJField`, `CPFCNPJField`).

## 5. Arquitetura multiempresa — leia com atenção

Este é o mecanismo mais importante e menos óbvio do projeto. Antes de mexer em
qualquer view de `cadastros` ou `usuarios`, entenda `usuarios/views.py`:

- Após o login, o usuário escolhe uma empresa ativa (`SelectCompanyView` /
  `ActivateCompanyView`), que é gravada em **sessão** (`active_company_id`).
- `ActiveCompanyRequiredMixin` (em `usuarios/views.py`) é herdado por praticamente
  todas as views de `cadastros` e do dashboard. Ele:
  - Redireciona para `select-company` se não houver empresa ativa na sessão;
  - Filtra automaticamente o `queryset` pela empresa ativa (`get_queryset`);
  - Associa automaticamente o objeto criado/editado à empresa ativa (`form_valid`);
  - Filtra as opções de campos `ForeignKey` dos formulários para mostrarem apenas
    registros da empresa ativa (`get_form`).
- Ou seja: **o isolamento entre empresas depende inteiramente desse mixin.**
  Qualquer nova view/model que precise de escopo por empresa deve herdar dele
  (ou replicar exatamente a mesma lógica de filtro) — não existe isolamento a
  nível de banco (middleware, schema, RLS etc.).
- `GroupRequiredMixin` (de `django-braces`) restringe ações a grupos do Django
  (hoje só existe o grupo `Manager`, criado automaticamente via `post_migrate`
  em `usuarios/apps.py`).

## 6. Perfis de usuário

Não há um model de "perfil/papel" explícito — o controle é feito via
`is_superuser`, pertencimento ao grupo `Manager` e às relações M2M
`Company.manager` / `Company.sales_rep`:

- **Administrador master** (`is_superuser=True`): cadastra empresas, gerentes e
  representantes; enxerga todas as empresas.
- **Gerente** (grupo `Manager` + em `Company.manager`): administra produtos,
  clientes e representantes da(s) própria(s) empresa(s); aprova pedidos (RF14 —
  ainda pendente, ver Seção 8).
- **Representante comercial** (em `Company.sales_rep`): lança pedidos para
  clientes da empresa ativa.

⚠️ **Limitação conhecida (RN02 não aplicada):** hoje qualquer usuário com acesso
à empresa ativa vê **todos** os pedidos da empresa, independentemente de quem os
criou. Não assuma que o escopo por representante já existe — se for pedido para
implementar isso, é trabalho novo, não correção de bug.

## 7. Convenções de código a seguir

- **Idioma:** comentários, `verbose_name`, mensagens de erro e templates estão em
  **português**; nomes de campos/classes Python estão em **inglês**
  (`Company`, `Client`, `unit_value`, `stock`...). Mantenha esse padrão.
- **`LANGUAGE_CODE = 'en-us'` é proposital**, não é esquecimento — está anotado em
  `usuarios/views.py`. Mudar para `pt-br` altera a formatação de números nos
  templates e quebra o JS de pedidos, que espera `data-price="12.50"` (ponto, não
  vírgula). Não altere sem revisar todo o JS de máscaras/preços.
- **Máscaras de CPF/CNPJ/telefone:** sempre reutilize `cadastros/masks.py` e os
  campos de `cadastros/forms.py` (`MaskedDigitsField` e subclasses) — não crie
  nova lógica de máscara/validação duplicada.
- **Views:** o projeto usa Class-Based Views genéricas do Django
  (`CreateView`/`UpdateView`/`DeleteView`/`ListView`/`DetailView`). Siga esse
  padrão em vez de introduzir function-based views novas, salvo necessidade clara.
- **Listagens paginadas:** herdam de `PaginatedListView` (em `cadastros/views.py`),
  que aceita `?per_page=10|20|40`. Reuse-a em vez de reimplementar paginação.
- **Cálculo de valores de pedido:** é feito no backend (`OrderCreate.form_valid`,
  com `transaction.atomic` e `select_for_update` no produto para evitar
  condição de corrida no estoque). Nunca confie em valores de total vindos do
  formulário/JS sem recalcular no servidor.
- **Estoque:** é decrementado dentro da mesma transação da criação do pedido.
  Qualquer alteração no fluxo de pedidos precisa preservar essa atomicidade.

## 8. Status dos requisitos funcionais (não redescubra isso do zero)

Fonte: documentação do TCC (capítulo de Resultados). Use como checklist de
prioridades ao propor novas funcionalidades:

| ID | Descrição | Situação |
|---|---|---|
| RF01 | Autenticação por login e senha | Atendido |
| RF02 | Cadastro de empresas | Atendido |
| RF03 | Cadastro de gerentes/representantes pelo admin master | Atendido |
| RF04 | Gerente cadastra representantes vinculados | Atendido |
| RF05 | Redefinição de senha via e-mail | Atendido |
| RF06 | Cadastro de produtos | Atendido |
| RF07 | Notificação por e-mail ao gerente | **Pendente** |
| RF08 | Criação de pedidos pelo representante | Atendido |
| RF09 | Adição de produtos/quantidades ao pedido | Atendido |
| RF10 | Cálculo automático dos valores do pedido | Atendido |
| RF11 | Edição do pedido pelo representante | Parcialmente atendido |
| RF12 | Duplicação de pedido | **Pendente** |
| RF13 | Visualização (gerente) dos pedidos da empresa | Atendido |
| RF14 | Aprovação/rejeição de pedidos | **Pendente** |
| RF15 | Representante vê apenas os próprios pedidos (RN02) | **Pendente** |

Outras limitações documentadas:
- Gráficos do painel gerencial (dashboard) ainda exibem dados de demonstração em
  parte da UI, apesar dos indicadores numéricos já usarem dados reais
  (ver `website/views.py:IndexView`).
- Não há suíte de testes automatizados (`tests.py` de cada app está vazio).
- Não há testes formais de usabilidade/desempenho.
- `app.yaml` usa `min_instances: 0` (escalonamento automático), o que pode
  introduzir latência de cold start incompatível com a meta de RNF04
  (resposta em até 3s).

## 9. Apps "casca" — não é código morto por acidente

- **`sigep/`**: models antigos comentados (Historico, Gerente, Representante,
  Cliente) — versão anterior do domínio, substituída pelo app `cadastros`. Sem
  urls/views ativos. Não reative sem confirmar com o mantenedor.
- **`license/`**: models comentados de um possível módulo de licenciamento/planos
  (`CompanyLicense`, `Plan`, `Recharge`) — é planejamento futuro, não implementado.
  Se for pedido para trabalhar em "licenciamento" ou "planos", comece por aqui,
  mas trate como funcionalidade nova, não como bug.

## 10. Como rodar o projeto localmente

```bash
# instalar dependências
pip install -r requirements.txt

# variáveis de ambiente (.env na raiz, ao lado de manage.py)
# obrigatório: DATABASE_URL=postgres://usuario:senha@host:5432/banco

# aplicar migrações
python manage.py migrate

# criar superusuário
python manage.py createsuperuser

# rodar servidor de desenvolvimento
python manage.py runserver

# após alterar models
python manage.py makemigrations
python manage.py migrate

# antes de deploy, gerar estáticos
python manage.py collectstatic
```

Fluxo de commit sugerido pelo próprio projeto está em `github.py` (script
interativo que roda `git add` + `git commit` + `git push`) — opcional, não
obrigatório usar.

## 11. Deploy

- Google App Engine (`gcloud app deploy`), config em `app.yaml`
  (`runtime: python312`, `gunicorn`, `automatic_scaling.min_instances: 0`).
- Estáticos servidos a partir de `static_gcloud/` (gerado por `collectstatic`).
- Banco: Neon Postgres, string de conexão via `DATABASE_URL`.

## 12. Débitos técnicos / cuidados de segurança para o agente sinalizar (não corrigir silenciosamente)

Estes pontos existem hoje no `settings.py` e são **decisões a confirmar com o
responsável antes de alterar**, pois podem refletir configuração provisória de
ambiente de desenvolvimento/TCC:

- `DEBUG = True` e `ALLOWED_HOSTS = ['*']` hardcoded.
- `SECRET_KEY` hardcoded no repositório (não vem de variável de ambiente).
- `django-debug-toolbar` ativo incondicionalmente no `MIDDLEWARE`.

Se for pedido para "preparar para produção", esses são os pontos a revisar
primeiro — mas não os altere como efeito colateral de uma tarefa não relacionada.

## 13. Diretrizes gerais para o agente

1. Antes de criar uma view/model novo em `cadastros`, verifique se ele precisa
   de escopo por empresa e, se sim, herde `ActiveCompanyRequiredMixin`.
2. Antes de adicionar validação de CPF/CNPJ/telefone, reuse `cadastros/masks.py`.
3. Não mude `LANGUAGE_CODE`, o formato de armazenamento de CPF/CNPJ/telefone
   (somente dígitos) ou a atomicidade do fluxo de criação de pedido sem avaliar
   o impacto descrito acima.
4. Ao implementar RF07, RF12, RF14 ou RF15 (Seção 8), primeiro releia
   `cadastros/models.py` (`Order`) e `cadastros/views.py` (`OrderCreate`,
   `OrderList`) — a base já existente deve ser estendida, não duplicada.
   RF14 (aprovação/rejeição) provavelmente exige um novo campo de status em
   `Order`, que hoje não existe.
5. Gere migrações (`makemigrations`) para qualquer alteração de `models.py` e
   inclua-as no mesmo commit/PR da mudança.
6. Não existem testes automatizados hoje — ao adicionar funcionalidade nova,
   é uma boa oportunidade para começar a popular os `tests.py` correspondentes,
   mas confirme com o mantenedor antes de tratar isso como obrigatório em toda
   tarefa.