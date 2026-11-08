from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class ImportacaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'importacao'
    verbose_name = "Importação de documentos"

    def ready(self):
        # Registra a tarefa de leitura da fila
        from . import services  # noqa: F401
        # Cada app de domínio que tiver <app>/importacao.py registra o seu importador (@registrar).
        # É assim que o importacao conhece os importadores sem importar nenhum app de domínio.
        autodiscover_modules("importacao")
