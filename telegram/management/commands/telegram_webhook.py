from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from telegram.cliente import obter_cliente


class Command(BaseCommand):
    help = "Registra no Telegram a URL do webhook e o segredo que estão no .env."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_WEBHOOK_URL or not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError("Preencha TELEGRAM_BOT_WEBHOOK_URL e TELEGRAM_WEBHOOK_SECRET no .env.")
        resultado = obter_cliente().chamar(
            "setWebhook",
            url=settings.TELEGRAM_BOT_WEBHOOK_URL,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query"],
            max_connections=settings.TELEGRAM_MAX_CONEXOES,
        )
        if resultado is None:
            raise CommandError("O Telegram recusou o webhook. O motivo está no log (Mensagens do Telegram, no admin).")
        self.stdout.write(self.style.SUCCESS("Webhook registrado: {}".format(settings.TELEGRAM_BOT_WEBHOOK_URL)))
