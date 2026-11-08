"""Regras do vínculo com o Telegram. O site e o bot chamam as mesmas funções."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from cadastros import consultas

from .models import CodigoVinculoTelegram, VinculoTelegram


def vinculo_valido(telegram_id):
    """Devolve o vínculo da pessoa, ou None. Usuário desativado no site não tem acesso pelo bot."""
    return VinculoTelegram.objects.select_related("usuario", "empresa").filter(
        telegram_id=telegram_id, usuario__is_active=True,
    ).first()


def empresa_do_vinculo(vinculo):
    """
    Empresa usada nos comandos, conferida a cada vez: o usuário pode ter saído dela no site.
    Com uma empresa só, ela é escolhida sem perguntar. Devolve None quando é preciso escolher.
    """
    empresas = consultas.empresas_do_usuario(vinculo.usuario)
    if vinculo.empresa_id and empresas.filter(pk=vinculo.empresa_id).exists():
        return vinculo.empresa
    primeiras = list(empresas[:2])
    if len(primeiras) == 1:
        return escolher_empresa(vinculo, primeiras[0].pk)
    return None


def escopo_da_importacao(vinculo):
    """
    O escopo das importações pelo bot: {"empresa": id}, como a empresa ativa no site. None quando
    a pessoa está em mais de uma empresa e ainda não escolheu a do bot; {} quando não está em
    nenhuma (aí o importador que precisa da empresa recusa com a própria mensagem).
    """
    empresa = empresa_do_vinculo(vinculo)
    if empresa is not None:
        return {"empresa": empresa.pk}
    return None if consultas.empresas_do_usuario(vinculo.usuario).exists() else {}


def escolher_empresa(vinculo, empresa_id):
    """Grava a empresa do bot, se o usuário tiver acesso a ela. Devolve a empresa, ou None."""
    empresa = consultas.empresas_do_usuario(vinculo.usuario).filter(pk=empresa_id).first()
    if empresa is not None:
        VinculoTelegram.objects.filter(pk=vinculo.pk).update(empresa=empresa)
        vinculo.empresa = empresa
    return empresa


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
