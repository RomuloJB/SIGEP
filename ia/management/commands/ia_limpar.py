from django.core.management.base import BaseCommand

from ia.manutencao import limpar_requisicoes
from ia.models import ConfiguracaoIA


class Command(BaseCommand):
    help = "Apaga as requisições de IA mais antigas que o prazo de retenção da configuração (não mexe no consumo)."

    def handle(self, *args, **options):
        dias = ConfiguracaoIA.obter().reter_requisicoes_dias
        if not dias:
            self.stdout.write("Retenção configurada como 0: a limpeza está desligada.")
            return
        apagadas = limpar_requisicoes()
        self.stdout.write(self.style.SUCCESS(
            "{} requisições de IA apagadas (mais antigas que {} dias).".format(apagadas, dias)
        ))
