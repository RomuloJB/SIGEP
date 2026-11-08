from django.core.management.base import BaseCommand

from importacao import services
from importacao.models import ConfiguracaoImportacao


class Command(BaseCommand):
    help = "Expira rascunhos esquecidos, destrava leituras presas e apaga importações encerradas antigas."

    def handle(self, *args, **options):
        config = ConfiguracaoImportacao.obter()
        expiradas = services.expirar()
        destravadas = services.destravar()
        apagadas = services.limpar()
        self.stdout.write(self.style.SUCCESS("Manutenção da importação concluída:"))
        self.stdout.write("- {} expiradas (para revisar há {} dias ou aguardando o tipo há {} h)".format(
            expiradas, config.pronta_expira_dias, config.aguardando_expira_horas))
        self.stdout.write("- {} leituras presas viraram \"Falhou\" (paradas há mais de {} min)".format(
            destravadas, config.leitura_trava_minutos))
        self.stdout.write("- {} importações encerradas apagadas (há mais de {} dias)".format(
            apagadas, config.reter_encerradas_dias))
