from django.core.management.base import BaseCommand

from telegram.manutencao import CONTADOR_PARADO_DIAS, limpar
from telegram.models import ConfiguracaoTelegram


class Command(BaseCommand):
    help = "Aplica a retenção do log do Telegram e apaga contadores parados e códigos de vínculo vencidos."

    def handle(self, *args, **options):
        config = ConfiguracaoTelegram.obter()
        resultado = limpar()
        self.stdout.write(self.style.SUCCESS("Limpeza do Telegram concluída:"))
        self.stdout.write("- {} mensagens apagadas (mais antigas que {} dias)".format(
            resultado["mensagens_apagadas"], config.reter_mensagens_dias))
        self.stdout.write("- JSON apagado de {} mensagens (mais antigas que {} dias)".format(
            resultado["conteudos_apagados"], config.reter_conteudo_dias))
        self.stdout.write("- {} contadores apagados (parados há mais de {} dias)".format(
            resultado["contadores_apagados"], CONTADOR_PARADO_DIAS))
        self.stdout.write("- {} códigos de vínculo vencidos apagados".format(resultado["codigos_apagados"]))
