from django.contrib import admin

from .models import ConfiguracaoIA, ConfiguracaoIAUsuario


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
