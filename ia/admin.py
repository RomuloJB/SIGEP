from django.contrib import admin

from .models import ConfiguracaoIA, ConfiguracaoIAUsuario, ConsumoIA, RequisicaoIA


@admin.register(ConfiguracaoIA)
class ConfiguracaoIAAdmin(admin.ModelAdmin):
    list_display = ("__str__", "atualizado_em")
    readonly_fields = ("atualizado_em",)

    def has_add_permission(self, request):
        # Linha única: só deixa adicionar enquanto ela não existir
        return super().has_add_permission(request) and not ConfiguracaoIA.objects.exists()


@admin.register(ConfiguracaoIAUsuario)
class ConfiguracaoIAUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "ia_habilitada", "limite_mensal")
    list_filter = ("ia_habilitada",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name")
    autocomplete_fields = ("usuario",)


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros gravados só pelo sistema: o admin apenas consulta."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RequisicaoIA)
class RequisicaoIAAdmin(SomenteLeituraAdmin):
    list_display = ("criado_em", "usuario", "finalidade", "situacao", "tentativa", "tokens_total", "duracao_ms", "modelo")
    list_filter = ("situacao", "origem", "finalidade", "provedor")
    search_fields = ("usuario__username", "finalidade", "contexto_hash", "arquivo_hash")
    date_hierarchy = "criado_em"
    list_select_related = ("usuario",)


@admin.register(ConsumoIA)
class ConsumoIAAdmin(SomenteLeituraAdmin):
    list_display = ("mes", "usuario", "tokens_total", "tokens_entrada", "tokens_saida", "requisicoes", "custo_estimado")
    list_filter = ("mes",)
    search_fields = ("usuario__username",)
    list_select_related = ("usuario",)
