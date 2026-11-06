"""Regras do vínculo com o Telegram. O site e o bot chamam as mesmas funções."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import CodigoVinculoTelegram, VinculoTelegram


def vinculo_valido(telegram_id):
    """Devolve o vínculo da pessoa, ou None. Usuário desativado no site não tem acesso pelo bot."""
    return VinculoTelegram.objects.select_related("usuario").filter(
        telegram_id=telegram_id, usuario__is_active=True,
    ).first()


def conectar(token, telegram_id, chat_id, username="", nome=""):
    """
    Troca o código por um vínculo e devolve esse vínculo, ou None se o código não valer.
    Tanto o usuário quanto a pessoa no Telegram ficam só com este vínculo novo.
    """
    codigo = CodigoVinculoTelegram.buscar_valido(token)
    if codigo is None or not codigo.usuario.is_active:
        return None

    agora = timezone.now()
    with transaction.atomic():
        # O filtro em usado_em garante o uso único: de dois /start simultâneos, só um marca o código
        if not CodigoVinculoTelegram.objects.filter(pk=codigo.pk, usado_em__isnull=True).update(usado_em=agora):
            return None
        # Apagar em vez de editar leva junto a espera de uma pergunta feita ao vínculo antigo
        VinculoTelegram.objects.filter(Q(usuario=codigo.usuario) | Q(telegram_id=telegram_id)).delete()
        return VinculoTelegram.objects.create(
            usuario=codigo.usuario, telegram_id=telegram_id, chat_id=chat_id,
            username=username, nome=nome, ultimo_uso=agora,
        )


def desconectar(usuario):
    """Apaga o vínculo do usuário. Devolve True se havia um."""
    apagados, _ = VinculoTelegram.objects.filter(usuario=usuario).delete()
    return apagados > 0


def registrar_uso(vinculo, chat_id):
    """Atualiza a conversa e o último uso de quem está conectado, no máximo uma vez por minuto."""
    agora = timezone.now()
    if vinculo.ultimo_uso and agora - vinculo.ultimo_uso < timedelta(seconds=settings.TELEGRAM_USO_INTERVALO_S):
        return
    VinculoTelegram.objects.filter(pk=vinculo.pk).update(chat_id=chat_id, ultimo_uso=agora)
