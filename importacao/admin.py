from django.contrib import admin

from .models import ConfiguracaoImportacao, Importacao


@admin.register(Importacao)
class ImportacaoAdmin(admin.ModelAdmin):
    """Só consulta: as mudanças passam pelos services, que conferem as transições e avisam o bot."""
    list_display = ("pk", "criado_em", "criado_por", "tipo", "origem", "situacao", "arquivo_nome", "tentativas")
    list_filter = ("situacao", "origem", "tipo")
    search_fields = ("criado_por__username", "arquivo_nome", "arquivo_hash")
    date_hierarchy = "criado_em"
    list_select_related = ("criado_por",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ConfiguracaoImportacao)
class ConfiguracaoImportacaoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "atualizado_em")
    readonly_fields = ("atualizado_em",)

    def has_add_permission(self, request):
        # Linha única: só deixa adicionar enquanto ela não existir
        return super().has_add_permission(request) and not ConfiguracaoImportacao.objects.exists()
