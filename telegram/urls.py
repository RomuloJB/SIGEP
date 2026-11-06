from django.urls import path

from .views import (
    ConectarTelegramView, ConexaoTelegramView, ConfiguracaoTelegramUpdate, DesconectarTelegramView,
    MensagemTelegramDetail, MensagemTelegramList, RemetenteTelegramLiberar, RemetenteTelegramList, webhook,
)

app_name = "telegram"

urlpatterns = [
    path("", ConexaoTelegramView.as_view(), name="conexao"),
    path("conectar/", ConectarTelegramView.as_view(), name="conectar"),
    path("desconectar/", DesconectarTelegramView.as_view(), name="desconectar"),
    path("log/", MensagemTelegramList.as_view(), name="mensagem-list"),
    path("log/<int:pk>/", MensagemTelegramDetail.as_view(), name="mensagem-detail"),
    path("remetentes/", RemetenteTelegramList.as_view(), name="remetente-list"),
    path("remetentes/<int:pk>/liberar/", RemetenteTelegramLiberar.as_view(), name="remetente-liberar"),
    path("configuracao/", ConfiguracaoTelegramUpdate.as_view(), name="configuracao"),
    path("webhook/", webhook, name="webhook"),
]
