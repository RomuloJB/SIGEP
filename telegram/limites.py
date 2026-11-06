"""Limites do bot por remetente. Os números vêm da ConfiguracaoTelegram."""
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import ConfiguracaoTelegram, LimiteTelegram

JANELA = timedelta(minutes=1)
AVISO_PAUSA = "⏸️ Você mandou muitas mensagens em pouco tempo. Vou fazer uma pausa de {} minutos."
AVISO_ARQUIVOS = "⏸️ Você mandou muitos arquivos em pouco tempo. Os extras foram recusados: envie de novo daqui a um minuto."


@dataclass(frozen=True)
class Veredito:
    seguir: bool
    aviso: str = ""


SEGUIR = Veredito(True)
DESCARTAR = Veredito(False)


def _abrir_janela(limite, agora):
    if limite.janela_inicio is None or agora - limite.janela_inicio >= JANELA:
        limite.janela_inicio = agora
        limite.mensagens = limite.arquivos = 0
        limite.avisou_arquivos = False


def _avaliar_conectado(limite, config, agora, arquivo):
    limite.mensagens += 1
    if limite.mensagens > config.mensagens_por_minuto:
        limite.bloqueado_ate = agora + timedelta(minutes=config.bloqueio_minutos)
        limite.aviso_em = agora
        return Veredito(False, AVISO_PAUSA.format(config.bloqueio_minutos))
    if not arquivo:
        return SEGUIR
    limite.arquivos += 1
    if limite.arquivos <= config.arquivos_por_minuto:
        return SEGUIR
    if limite.avisou_arquivos:
        return DESCARTAR
    limite.avisou_arquivos = True
    limite.aviso_em = agora
    return Veredito(False, AVISO_ARQUIVOS)


def _avaliar_desconhecido(limite, config, agora, comando):
    limite.mensagens += 1
    if limite.mensagens > config.desconhecido_mensagens_por_minuto:
        limite.bloqueado_ate = agora + timedelta(minutes=config.desconhecido_bloqueio_minutos)
        return DESCARTAR
    # Comando sempre segue: quem já recebeu o aviso precisa do /start <código> para se conectar
    avisado = limite.aviso_em and agora - limite.aviso_em < timedelta(hours=config.desconhecido_aviso_horas)
    return DESCARTAR if avisado and not comando else SEGUIR


def verificar(telegram_id, conectado, arquivo=False, comando=False):
    """Conta a mensagem e diz se ela segue. O aviso do veredito é enviado por quem chamou, fora da trava."""
    config = ConfiguracaoTelegram.obter()
    agora = timezone.now()
    with transaction.atomic():
        limite, _ = LimiteTelegram.objects.select_for_update().get_or_create(telegram_id=telegram_id)
        limite.total += 1
        if limite.bloqueado:
            veredito = DESCARTAR
        else:
            _abrir_janela(limite, agora)
            if conectado:
                veredito = _avaliar_conectado(limite, config, agora, arquivo)
            else:
                veredito = _avaliar_desconhecido(limite, config, agora, comando)
        if not veredito.seguir:
            limite.descartadas += 1
        limite.save()
    return veredito


def _marcar_aviso(telegram_id, campo, intervalo):
    """Grava o momento do aviso, se o intervalo já passou. O UPDATE com filtro garante um aviso só."""
    agora = timezone.now()
    vencido = Q(**{campo + "__isnull": True}) | Q(**{campo + "__lte": agora - intervalo})
    return LimiteTelegram.objects.filter(vencido, telegram_id=telegram_id).update(**{campo: agora}) > 0


def pode_avisar_conexao(telegram_id):
    intervalo = timedelta(hours=ConfiguracaoTelegram.obter().desconhecido_aviso_horas)
    return _marcar_aviso(telegram_id, "aviso_em", intervalo)


def pode_avisar_erro(telegram_id):
    return _marcar_aviso(telegram_id, "erro_avisado_em", timedelta(minutes=settings.TELEGRAM_AVISO_ERRO_MIN))


def liberar(limite):
    """Encerra o bloqueio e zera a janela, para a próxima mensagem não bloquear de novo."""
    LimiteTelegram.objects.filter(pk=limite.pk).update(
        bloqueado_ate=None, janela_inicio=None, mensagens=0, arquivos=0, avisou_arquivos=False,
    )
