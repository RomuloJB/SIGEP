# SIGEP: Sistema de Gestão de Pedidos

Aplicação web em Django para gestão de pedidos comerciais de empresas que trabalham com
representantes de vendas. É multiempresa e roda no Google App Engine com banco PostgreSQL (Neon).

A arquitetura, as convenções de código e o estado dos requisitos estão em [AGENT.md](AGENT.md).
Os comandos do dia a dia estão em [commands.txt](commands.txt).

## Como rodar

```bash
pip install -r requirements.txt
# copie o .env.example para .env e preencha pelo menos SECRET_KEY e DATABASE_URL
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Testes (o banco de teste fica no Neon, então é preciso internet):

```bash
python manage.py test --keepdb
```

## Bot do Telegram

O app `telegram` é mais uma porta para o sistema: a pessoa conecta o usuário do site ao
Telegram e consulta aprovações, pedidos e estoque pelo celular. O bot não tem regra de negócio
própria; ele usa as mesmas consultas do site.

### 1. Criar o bot no BotFather

1. No Telegram, abra o **@BotFather** (o que tem selo azul) e envie `/newbot`.
2. Informe o nome de exibição (ex.: `SIGEP`) e o username, que precisa terminar em `bot`
   (ex.: `sigep_pedidos_bot`).
3. Guarde o token que ele devolve. Ele é a senha do bot: fica só no `.env`, nunca no código,
   num commit ou num chat. Se vazar, gere outro com `/revoke` no BotFather.

Nome, descrição e menu de comandos não precisam ser configurados no BotFather: o comando
`telegram_definir_webhook` aplica os textos de `telegram/comandos.py`.

### 2. Variáveis do .env

| Variável | O que é |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token devolvido pelo BotFather |
| `TELEGRAM_BOT_USERNAME` | Username do bot, sem o `@` (monta os links `t.me/...`) |
| `TELEGRAM_BOT_WEBHOOK_URL` | URL pública HTTPS do webhook, terminada em `/telegram/webhook/` |
| `TELEGRAM_WEBHOOK_SECRET` | Frase aleatória que você gera (letras, números, `_` e `-`) |
| `SITE_URL` | Endereço público do site, sem barra no fim. Botões que abrem o site só aparecem com `https://` |
| `ALLOWED_HOSTS` | Domínios extras aceitos pelo Django, separados por vírgula (ex.: o do ngrok) |
| `TAREFAS_SEGREDO` | Segredo das rotas de manutenção, para chamá-las fora do cron do App Engine |

Para gerar um segredo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Limites por pessoa e prazos de retenção do log não ficam no `.env`: são ajustados na tela
**Configuração do Telegram** (`/telegram/configuracao/`, só superusuário).

### 3. Desenvolvimento com ngrok

O Telegram só chama endereços HTTPS públicos, e o `localhost` não é um deles. O ngrok cria um
túnel até a sua máquina.

Uma vez por máquina:

```bash
winget install ngrok.ngrok
ngrok config add-authtoken SEU_TOKEN_DO_NGROK
```

O authtoken fica no [painel do ngrok](https://dashboard.ngrok.com/get-started/your-authtoken).
Se o terminal não reconhecer o `ngrok` logo depois de instalar, feche e abra o VS Code.

Para testar, use dois terminais:

```bash
ngrok http 8000            # terminal 1: anote o endereço https://... da linha Forwarding
python manage.py runserver # terminal 2
```

Com o endereço do ngrok (ex.: `abc123.ngrok-free.app`), preencha o `.env`:

```env
ALLOWED_HOSTS=abc123.ngrok-free.app
SITE_URL=https://abc123.ngrok-free.app
TELEGRAM_BOT_WEBHOOK_URL=https://abc123.ngrok-free.app/telegram/webhook/
```

Depois reinicie o `runserver` e registre o webhook (próximo passo). Sempre que o endereço do
ngrok mudar, repita: atualizar o `.env`, reiniciar e registrar.

O painel do ngrok em <http://127.0.0.1:4040> mostra cada requisição e tem o botão **Replay**,
que reenvia o mesmo update: serve para conferir que o bot não responde duas vezes.

### 4. Registrar o webhook

```bash
python manage.py telegram_definir_webhook
```

O comando aplica o nome, as descrições e o menu de comandos e registra o webhook com o segredo.
Ele recusa URL sem `https://` e completa `/telegram/webhook/` quando a URL é só a raiz do site.
As mensagens que chegarem enquanto o servidor estiver fora não são descartadas.

Rode de novo sempre que mudar a URL, o segredo ou os textos de `telegram/comandos.py`.

### 5. Conferir com --info

```bash
python manage.py telegram_definir_webhook --info
```

Mostra a URL registrada no Telegram, as mensagens pendentes e o último erro de entrega. É o
primeiro lugar a olhar quando o bot "para de responder". O esperado é a URL do `.env`,
0 pendentes e nenhum erro recente.

Para desligar o bot sem apagar nada: `python manage.py telegram_definir_webhook --remover`.

### 6. Produção (App Engine)

1. No `.env` de produção, use o endereço do App Engine (ex.: `https://seu-projeto.appspot.com`)
   em `SITE_URL` e em `TELEGRAM_BOT_WEBHOOK_URL`. O `*.appspot.com` já tem HTTPS.
2. Publique o site e, na primeira vez ou quando o `cron.yaml` mudar, o agendador:

   ```bash
   gcloud app deploy
   gcloud app deploy cron.yaml
   ```

3. Registre o webhook com o `.env` de produção e confira com `--info`.

O bot de produção e o de desenvolvimento não podem usar o mesmo token ao mesmo tempo: o
Telegram guarda um único webhook por bot, e o último registrado vale. Para testar sem derrubar
a produção, crie um segundo bot no BotFather.

### 7. Manutenção do log

`python manage.py telegram_limpar` aplica os prazos da Configuração do Telegram: apaga o JSON
das mensagens antigas, depois as próprias mensagens, os contadores parados há mais de 7 dias
(menos os que estão com bloqueio valendo) e os códigos de vínculo vencidos.

No App Engine, o `cron.yaml` faz isso todo dia às 03:00 chamando `GET /telegram/manutencao/`.
A rota só aceita o cabeçalho `X-Appengine-Cron` dentro do App Engine (que o remove das
requisições externas) ou o cabeçalho `X-Tarefas-Segredo` igual ao `TAREFAS_SEGREDO` do `.env`:

```bash
curl -H "X-Tarefas-Segredo: SEU_SEGREDO" https://seu-projeto.appspot.com/telegram/manutencao/
```

### Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `--info` mostra outra URL | O endereço mudou (ngrok ou outra máquina): rode `telegram_definir_webhook` de novo |
| `--info` mostra pendentes e erro `Wrong response from the webhook: 400 Bad Request` | O domínio não está em `ALLOWED_HOSTS` no `.env`, ou o `runserver` não foi reiniciado |
| `--info` mostra erro `403 Forbidden` | O segredo do `.env` mudou depois do registro: rode o comando de novo |
| O bot não responde e não há erro | Você pode estar bloqueado pelos limites: veja **Remetentes do Telegram** (`/telegram/remetentes/`) e use **Liberar** |
| O que o bot recebeu e respondeu | **Log do Telegram** (`/telegram/log/`, só superusuário) |
