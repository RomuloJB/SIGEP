from django.contrib import admin

from .models import ConfiguracaoTelegram, LimiteTelegram, MensagemTelegram, VinculoTelegram


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros gravados só pelo sistema: o admin apenas consulta."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VinculoTelegram)
class VinculoTelegramAdmin(admin.ModelAdmin):
    list_display = ("usuario", "username", "nome", "telegram_id", "vinculado_em", "ultimo_uso")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "username", "nome", "telegram_id")
    autocomplete_fields = ("usuario",)
    list_select_related = ("usuario",)


@admin.register(ConfiguracaoTelegram)
class ConfiguracaoTelegramAdmin(admin.ModelAdmin):
    list_display = ("__str__", "atualizado_em")
    readonly_fields = ("atualizado_em",)

    def has_add_permission(self, request):
        # Linha única: só deixa adicionar enquanto ela não existir
        return super().has_add_permission(request) and not ConfiguracaoTelegram.objects.exists()


@admin.register(MensagemTelegram)
class MensagemTelegramAdmin(SomenteLeituraAdmin):
    list_display = ("criado_em", "direcao", "tipo", "metodo_api", "usuario", "chat_id", "situacao", "status_http", "duracao_ms")
    list_filter = ("direcao", "situacao", "tipo", "metodo_api")
    search_fields = ("usuario__username", "texto", "telegram_id", "chat_id", "update_id")
    date_hierarchy = "criado_em"
    list_select_related = ("usuario",)


@admin.register(LimiteTelegram)
class LimiteTelegramAdmin(SomenteLeituraAdmin):
    list_display = ("telegram_id", "mensagens", "arquivos", "bloqueado_ate", "total", "descartadas", "ultima_vez")
    search_fields = ("telegram_id",)
