"""
Configura o bot no Telegram com o .env e os textos de telegram/comandos.py: nome, descrições,
menu de comandos e webhook. Rode de novo sempre que mudar a URL, o segredo ou os textos.

    python manage.py telegram_definir_webhook             # configura tudo
    python manage.py telegram_definir_webhook --info      # o que está registrado no Telegram agora
    python manage.py telegram_definir_webhook --remover   # desliga o webhook
"""
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from telegram.cliente import obter_cliente
from telegram.comandos import COMANDOS_DO_MENU, DESCRICAO_CURTA_DO_BOT, DESCRICAO_DO_BOT, NOME_DO_BOT
from telegram.models import MensagemTelegram

ATUALIZACOES = ["message", "callback_query"]
MOTIVO_DESCONHECIDO = "o Telegram não aceitou (detalhes no Log do Telegram)"


def url_do_webhook(url):
    """
    A URL que vai para o Telegram. Só a raiz do site ganha o caminho do webhook; sem a barra
    final, o APPEND_SLASH do Django responderia ao POST com um redirecionamento.
    """
    partes = urlsplit(url.strip())
    if partes.scheme != "https" or not partes.netloc:
        raise CommandError(
            "TELEGRAM_BOT_WEBHOOK_URL precisa começar com https:// (o Telegram recusa http). Está assim: {}".format(url)
        )
    caminho = reverse("telegram:webhook")
    if partes.path not in ("", "/") and partes.path.rstrip("/") + "/" != caminho:
        raise CommandError(
            "TELEGRAM_BOT_WEBHOOK_URL deve terminar em {} ou ser só a raiz do site. Está assim: {}".format(caminho, url)
        )
    return urlunsplit((partes.scheme, partes.netloc, caminho, "", ""))


class Command(BaseCommand):
    help = "Configura o bot no Telegram: nome, descrições, menu de comandos e webhook."

    def add_arguments(self, parser):
        opcoes = parser.add_mutually_exclusive_group()
        opcoes.add_argument(
            "--info", action="store_true", help="Mostra o webhook registrado no Telegram: URL, pendentes e último erro.",
        )
        opcoes.add_argument(
            "--remover", action="store_true", help="Desliga o webhook. As mensagens pendentes não são descartadas.",
        )

    def handle(self, *args, **opcoes):
        self.cliente = obter_cliente()
        self.inicio = timezone.now()
        if opcoes["info"]:
            self.exigir("TELEGRAM_BOT_TOKEN")
            self.mostrar_info()
        elif opcoes["remover"]:
            self.exigir("TELEGRAM_BOT_TOKEN")
            self.remover()
        else:
            self.exigir("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_WEBHOOK_URL", "TELEGRAM_WEBHOOK_SECRET")
            self.definir(url_do_webhook(settings.TELEGRAM_BOT_WEBHOOK_URL))

    def exigir(self, *nomes):
        faltando = [nome for nome in nomes if not getattr(settings, nome)]
        if faltando:
            raise CommandError("Preencha no .env: {}.".format(", ".join(faltando)))

    # ─── Configurar ───────────────────────────────────────────────────────────

    def definir(self, url):
        resultados = [
            self.definir_texto("Nome", "MyName", "name", NOME_DO_BOT),
            self.definir_texto("Descrição", "MyDescription", "description", DESCRICAO_DO_BOT),
            self.definir_texto("Descrição curta", "MyShortDescription", "short_description", DESCRICAO_CURTA_DO_BOT),
            self.passo("Menu de comandos", "setMyCommands", commands=[
                {"command": nome, "description": descricao} for nome, descricao in COMANDOS_DO_MENU
            ]),
            self.passo("Botão de menu", "setChatMenuButton", menu_button={"type": "commands"}),
            # Sem drop_pending_updates: as mensagens que chegarem durante um deploy não se perdem
            self.passo(
                "Webhook: {}".format(url), "setWebhook", url=url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                allowed_updates=ATUALIZACOES, max_connections=settings.TELEGRAM_MAX_CONEXOES,
            ),
        ]
        falhas = resultados.count(False)
        if falhas:
            raise CommandError("{} passo(s) falharam. Corrija e rode o comando de novo.".format(falhas))
        self.stdout.write(self.style.SUCCESS("Bot configurado. Confira com: python manage.py telegram_definir_webhook --info"))

    def definir_texto(self, rotulo, metodo, campo, valor):
        """O Telegram limita a frequência do setMyName e afins: só envia quando o texto mudou."""
        atual = self.cliente.chamar("get" + metodo)
        if isinstance(atual, dict) and atual.get(campo) == valor:
            self.stdout.write(self.style.SUCCESS("[ok] {}: já estava atualizado".format(rotulo)))
            return True
        return self.passo(rotulo, "set" + metodo, **{campo: valor})

    def passo(self, rotulo, metodo, **params):
        if self.cliente.chamar(metodo, **params) is None:
            self.stderr.write("[erro] {}: {}".format(rotulo, self.motivo(metodo)))
            return False
        self.stdout.write(self.style.SUCCESS("[ok] {}".format(rotulo)))
        return True

    def motivo(self, metodo):
        """A descrição do erro que o cliente gravou no log, já com o token mascarado."""
        erro = MensagemTelegram.objects.filter(
            direcao=MensagemTelegram.Direcao.SAIDA, metodo_api=metodo,
            situacao=MensagemTelegram.Situacao.FALHOU, criado_em__gte=self.inicio,
        ).order_by("-pk").values_list("erro", flat=True).first()
        return erro or MOTIVO_DESCONHECIDO

    # ─── --info e --remover ───────────────────────────────────────────────────

    def mostrar_info(self):
        info = self.cliente.chamar("getWebhookInfo")
        if not isinstance(info, dict):
            raise CommandError("Não consegui consultar o Telegram: {}".format(self.motivo("getWebhookInfo")))

        registrada = info.get("url") or ""
        if registrada:
            self.stdout.write(self.style.SUCCESS("URL registrada: {}".format(registrada)))
        else:
            self.stderr.write("Nenhum webhook registrado: o bot não recebe mensagens.")
        esperada = self.url_do_env()
        if esperada and registrada != esperada:
            self.stderr.write("A URL do .env é outra ({}). Rode o comando sem --info para atualizar.".format(esperada))

        pendentes = info.get("pending_update_count") or 0
        texto = "Mensagens pendentes: {}".format(pendentes)
        if pendentes:
            self.stderr.write(texto)  # o Telegram não está conseguindo entregar
        else:
            self.stdout.write(self.style.SUCCESS(texto))

        if info.get("last_error_date"):
            momento = timezone.localtime(datetime.fromtimestamp(info["last_error_date"], tz=dt_timezone.utc))
            self.stderr.write("Último erro: {:%d/%m/%Y %H:%M}: {}".format(momento, info.get("last_error_message", "")))
        else:
            self.stdout.write(self.style.SUCCESS("Nenhum erro recente."))

    def url_do_env(self):
        if not settings.TELEGRAM_BOT_WEBHOOK_URL:
            return ""
        try:
            return url_do_webhook(settings.TELEGRAM_BOT_WEBHOOK_URL)
        except CommandError:
            return ""

    def remover(self):
        if self.cliente.chamar("deleteWebhook") is None:
            raise CommandError("Não consegui remover o webhook: {}".format(self.motivo("deleteWebhook")))
        self.stdout.write(self.style.SUCCESS(
            "Webhook removido: o bot para de receber mensagens até você rodar o comando sem --remover."
        ))
