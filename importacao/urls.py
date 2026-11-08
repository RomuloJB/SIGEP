from django.urls import path

from .views import (
    ConfiguracaoImportacaoUpdate, ImportacaoDescartar, ImportacaoDetail, ImportacaoEscolherTipo, ImportacaoList,
    ImportacaoRevisar, ImportacaoTentarDeNovo, NovaImportacaoView, TarefaView,
)

app_name = "importacao"

urlpatterns = [
    path("", ImportacaoList.as_view(), name="lista"),
    path("nova/", NovaImportacaoView.as_view(), name="nova"),
    path("<int:pk>/", ImportacaoDetail.as_view(), name="detalhe"),
    path("<int:pk>/revisar/", ImportacaoRevisar.as_view(), name="revisar"),
    path("<int:pk>/descartar/", ImportacaoDescartar.as_view(), name="descartar"),
    path("<int:pk>/tipo/", ImportacaoEscolherTipo.as_view(), name="escolher-tipo"),
    path("<int:pk>/tentar-de-novo/", ImportacaoTentarDeNovo.as_view(), name="tentar-de-novo"),
    path("configuracao/", ConfiguracaoImportacaoUpdate.as_view(), name="configuracao"),
    # Chamada pelo Cloud Tasks: sem login e sem redirecionamento
    path("tarefas/<str:nome>/", TarefaView.as_view(), name="tarefa"),
]
