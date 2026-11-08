from django.apps import AppConfig


class TelegramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telegram'
    verbose_name = "Telegram"

    def ready(self):
        # Registra a tarefa de leitura e o receptor que mantém o cartão da importação em dia
        from . import importacoes, signals  # noqa: F401
