from django.urls import path

from .views import (
    ConfiguracaoIAUpdate, ConfiguracaoIAUsuarioPadrao, ConfiguracaoIAUsuarioUpdate, MeuConsumoView,
    RequisicaoIADetail, RequisicaoIAList, TestarConexaoView, UsuarioIAList,
)

app_name = "ia"

urlpatterns = [
    path("requisicoes/", RequisicaoIAList.as_view(), name="requisicao-list"),
    path("requisicoes/<int:pk>/", RequisicaoIADetail.as_view(), name="requisicao-detail"),
    path("meu-consumo/", MeuConsumoView.as_view(), name="meu-consumo"),
    path("configuracao/", ConfiguracaoIAUpdate.as_view(), name="configuracao"),
    path("configuracao/testar/", TestarConexaoView.as_view(), name="testar-conexao"),
    path("usuarios/", UsuarioIAList.as_view(), name="usuario-list"),
    path("usuarios/<int:usuario_id>/", ConfiguracaoIAUsuarioUpdate.as_view(), name="usuario-update"),
    path("usuarios/<int:usuario_id>/padrao/", ConfiguracaoIAUsuarioPadrao.as_view(), name="usuario-padrao"),
]
