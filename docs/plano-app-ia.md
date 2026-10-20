# Plano do app `ia`

Levantamento feito em 2026-10-16, só por leitura do projeto (branch `dev`). Nenhum arquivo além deste
foi criado ou alterado.

## 1. Visão do projeto

**Apps** (`naes2026/settings.py:37-55`):

| App | O que faz |
|---|---|
| `website` | Dashboard (`IndexView`, com gráficos de vendas da empresa ativa), páginas about/contact. Template base do sistema. |
| `usuarios` | Login/logout, troca de senha, cadastro público (`register`), escolha da empresa ativa (`SelectCompanyView`/`ActivateCompanyView`), gestão de usuários só para superusuário. Não tem models. Contém os mixins centrais (`BaseLoginMixin`, `ActiveCompanyRequiredMixin`, `SuperuserRequiredMixin`). |
| `cadastros` | Núcleo do domínio: `User_Profile`, `Company`, `Client`, `Product`, `Order`, `ProductOrder`. CBVs genéricas, `PaginatedFilterView` + django-filter, máscaras em `masks.py`. |
| `sigep` | Casca: models antigos comentados, sem views ativas. |
| `license` | Casca: models comentados de planos/licenças por empresa (`CompanyLicense`, `Plan`, `Recharge`). **Não está em `INSTALLED_APPS`.** |

Terceiros instalados como app: `crispy_forms`, `crispy_bootstrap5`, `debug_toolbar`, `django_filters`.
`django-braces` é usado só pelos mixins (`GroupRequiredMixin`, grupo `Manager` criado em `usuarios/apps.py`).

- **Django:** 5.2.11 (`requirements.txt`); Python 3.12 (local e `app.yaml`).
- **Model de usuário:** `auth.User` padrão (não há `AUTH_USER_MODEL`). Dados pessoais ficam em
  `cadastros.User_Profile` (1:1, `related_name='profile'`: nome, telefone, CPF).
- **TIME_ZONE:** `America/Sao_Paulo`, `USE_TZ = True`, `LANGUAGE_CODE = 'pt-br'`.
- **.env:** carregado com `python-dotenv` em `naes2026/settings.py:21` (`load_dotenv(BASE_DIR / ".env")`);
  as variáveis são lidas com `os.getenv`. Hoje o `.env` só tem `DATABASE_URL` (Postgres no Neon).
  O `.env` está no `.gitignore`, mas **não** no `.gcloudignore`, então sobe junto no deploy do App Engine
  (é assim que `DATABASE_URL` chega à produção).
- **Template base:** `website/templates/website/model.html`. Blocos: `extra_css`, `sidenav`, `content`,
  `scripts` (o bloco `scripts` já traz Chart.js e os scripts do dashboard; quem sobrescreve perde isso).
  As telas de cadastro estendem `cadastros/form.html`, que acrescenta `breadcrumb` e `cadastros_content`.
- **CSS:** Bootstrap 5 (tema SB Admin compilado em `static/css/styles.css`; JS do Bootstrap 5.2.3 via CDN),
  Font Awesome 6.3, jQuery 3.7.1, Bootbox 6, DataTables 2.1.8, formulários com crispy-bootstrap5.
- **Chave primária:** inteira (`DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`). Nenhum UUID.
- **Entidade dona dos dados:** `cadastros.Company` (multiempresa). O usuário se liga a ela por dois M2M,
  `Company.manager` (gerentes) e `Company.sales_rep` (representantes). Superusuário acessa todas.
  A empresa ativa fica na sessão (`active_company_id`) e o isolamento depende de
  `ActiveCompanyRequiredMixin` (`usuarios/views.py:72`): não há isolamento no banco.
- **Testes:** todos os `tests.py` estão vazios. O banco é sempre o Postgres do `DATABASE_URL`
  (settings levanta erro se não houver), então `manage.py test` hoje criaria o banco de teste no Neon.
- **Execução em produção:** App Engine, `gunicorn --workers 1 --threads 4`, `min_instances: 0`.

## 2. O que já existe de IA

- **google-genai:** não está no `requirements.txt` nem instalado no ambiente local.
- **Models de configuração de IA:** nenhum.
- **Chamadas a modelos de IA:** nenhuma.

Busca feita no projeto inteiro (ignorando `venv`, `.venv`, `node_modules`, `migrations`, `.git`) por
`google.genai`, `from google import genai`, `google.generativeai`, `openai`, `anthropic`, `GEMINI` e
`API_KEY`, sem diferenciar maiúsculas: zero ocorrências. O `.env` também não tem chave de IA.

## 3. Propostas

**Dono da cota: a empresa (`cadastros.Company`).**
Motivo: o sistema é multiempresa, os dados e o custo pertencem à empresa, e o planejamento de planos em
`license/` também é por empresa. Cada registro de chamada guarda também o usuário, para auditoria e para
ver quem consome mais dentro da empresa. A empresa da chamada é a empresa ativa da sessão, a mesma que
`ActiveCompanyRequiredMixin` já resolve.

**Chamadas existentes:** nenhuma; nada a mapear.

**Chatbot (a criar depois):**

| Item | Proposta | Motivo |
|---|---|---|
| finalidade | `chatbot_responder` | Padrão `app_acao`, supondo um app `chatbot` cuja ação é responder a uma mensagem. Se o chatbot ficar dentro do app `ia`, vira `ia_chatbot`. |
| referência | `conversa:<id>` (ex.: `conversa:42`) | Agrupa todas as chamadas de uma mesma conversa sem carregar dado pessoal. O id é inteiro, como o resto do projeto. Empresa e usuário já ficam em campos próprios do registro, então não entram na referência. |

Formato geral sugerido para a referência de outras finalidades: `<entidade>:<id>` em minúsculas
(ex.: `pedido:123`), nunca nome, CPF/CNPJ ou texto livre.

## 4. Riscos

- **Chave no código ou no banco:** hoje não há chave de IA em lugar nenhum. Cuidados:
  - `GEMINI_API_KEY` deve ir só no `.env`, nunca no `app.yaml` (que é versionado e tem um bloco
    `env_variables`) nem no model de configuração.
  - O `.env` vai no pacote de deploy porque o `.gcloudignore` não o exclui; quem tiver acesso ao código
    publicado no App Engine vê a chave.
  - `DEBUG = True` e `ALLOWED_HOSTS = ['*']` também em produção: a página de erro do Django mostra as
    variáveis locais de cada frame. Se `gemini.py` tiver a chave numa variável local e der exceção, ela
    aparece na tela. Mitigar com `@sensitive_variables` ou lendo a chave sem guardá-la em variável local.
  - `SECRET_KEY` hardcoded no repositório (débito já registrado no `AGENT.md`, não é desta tarefa).
- **Dados pessoais que iriam para a IA:**
  - `Client` tem nome, CPF/CNPJ, endereço e cidade; `User_Profile` tem nome, CPF e telefone; `Order`
    tem endereço. Um chatbot sobre pedidos e clientes tende a mandar isso ao Gemini (LGPD; no plano
    gratuito do Gemini o Google pode usar os dados para treino).
  - Sugestão: não enviar CPF/CNPJ nem telefone e não gravar o texto da conversa no registro de chamadas.
- **Vazamento entre empresas:** o isolamento depende de cada view herdar `ActiveCompanyRequiredMixin`.
  Qualquer consulta que o chatbot fizer para montar o contexto precisa filtrar pela empresa ativa. Além
  disso, a RN02 não está aplicada (representante vê todos os pedidos da empresa); o chatbot herdaria isso.
- **Falta de limite:** hoje não existe nenhum. Além da cota mensal, faltam limite de tokens de saída por
  chamada, tamanho máximo da entrada e timeout. Sem trava, duas chamadas simultâneas podem passar da cota
  juntas (verificação e gravação não são atômicas).
- **Chamada síncrona:** com 1 worker e 4 threads, cada chamada lenta ao Gemini prende uma thread; 4
  conversas simultâneas travam o site inteiro. O timeout precisa ser curto e configurável.
- **Prompt injection:** nomes de clientes, descrições de produtos e endereços são texto livre digitado
  por usuários e iriam para o prompt.
- **Testes e banco:** `manage.py test ia` hoje cria o banco de teste no Neon. Precisa de internet e
  permissão `CREATEDB`, o que contraria a regra "testes sem internet".
- **Fuso da cota:** o mês da cota tem que ser o mês civil em `America/Sao_Paulo` (`timezone.localdate()`,
  como já faz `website/views.py:ultimos_meses`), não em UTC; senão a virada acontece às 21h do último dia.

## 5. Perguntas

1. O dono da cota é a empresa (`Company`) ou o usuário? E uma chamada sem empresa ativa na sessão
   (por exemplo, superusuário que ainda não escolheu empresa) deve ser recusada?
   Sugestão: a empresa ativa é a dona da cota, o registro guarda também o usuário, e a chamada sem
   empresa ativa é recusada.
2. A cota mensal é um valor único para todas as empresas ou pode variar por empresa?
   Sugestão: um valor padrão na configuração de IA, mais uma exceção opcional por empresa guardada no
   próprio app `ia` (sem alterar o model `Company`).
3. O que acontece quando a empresa atinge a cota?
   Sugestão: a chamada é bloqueada antes de ir ao Gemini e fica registrada com situação de bloqueio. A
   checagem é "consumo do mês ≥ cota", então a última chamada pode passar um pouco da cota. O mês é o
   mês civil em `America/Sao_Paulo`.
4. O registro de cada chamada guarda o texto enviado e a resposta, ou só os metadados?
   Sugestão: só metadados (usuário, empresa, finalidade, referência, modelo, tokens, duração, situação)
   e uma mensagem de erro curta. Nada de texto do prompt nem da resposta (LGPD).
5. Quem pode abrir a tela de configuração (modelo, cotas, limites, prazos, preços)?
   Sugestão: só superusuário, usando `SuperuserRequiredMixin` de `usuarios/views.py`.
6. Os testes podem rodar num banco local em vez do Neon? Isso exige mexer em uma linha do
   `naes2026/settings.py`.
   Sugestão: quando o comando for `test`, usar SQLite em memória; o resto do settings fica igual.
