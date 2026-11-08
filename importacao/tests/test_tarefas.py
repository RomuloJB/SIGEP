import base64
import json
import os
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.urls import reverse

from importacao import services, tarefas
from importacao.models import ArquivoTemporario, Importacao

from .base import ImportacaoTestCase, png, resposta

S = Importacao.Situacao
SEGREDO = "segredo-das-tarefas"


class FilaImediataTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        patch = mock.patch("importacao.services.chamar_ia", return_value=resposta(nome="Vendas"))
        self.chamar_ia = patch.start()
        self.addCleanup(patch.stop)

    def test_leitura_roda_so_depois_do_commit_e_apaga_o_arquivo(self):
        importacao = self.criar()

        with self.captureOnCommitCallbacks(execute=True):
            services.guardar_arquivo(importacao, png(), "image/png")
            services.agendar_leitura(importacao)
            self.chamar_ia.assert_not_called()

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PRONTA)
        self.assertFalse(ArquivoTemporario.objects.exists())

    def test_sem_o_arquivo_guardado_a_leitura_falha(self):
        importacao = self.criar()

        with self.captureOnCommitCallbacks(execute=True):
            services.agendar_leitura(importacao)

        importacao.refresh_from_db()
        self.assertEqual((importacao.situacao, importacao.mensagem_erro), (S.FALHOU, services.MSG_ARQUIVO_SUMIU))

    @override_settings(TAREFAS_BACKEND="desconhecido")
    def test_fila_que_recusa_vira_falha_e_nunca_fica_lendo(self):
        importacao = self.criar()

        with self.assertLogs("importacao.tarefas", "ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                services.agendar_leitura(importacao)

        importacao.refresh_from_db()
        self.assertEqual((importacao.situacao, importacao.mensagem_erro), (S.FALHOU, services.MSG_FILA))

    def test_tarefa_desconhecida_e_erro_de_programacao(self):
        with self.assertRaises(ValueError):
            tarefas.enfileirar("nao.existe")


@override_settings(TAREFAS_BACKEND="cloud_tasks", TAREFAS_FILA="projects/p/locations/l/queues/q")
class CloudTasksTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        ambiente = mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": SEGREDO})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        credenciais = mock.patch("google.auth.default", return_value=(mock.Mock(), "p"))
        credenciais.start()
        self.addCleanup(credenciais.stop)
        sessao = mock.patch("google.auth.transport.requests.AuthorizedSession")
        self.sessao = sessao.start().return_value
        self.addCleanup(sessao.stop)
        self.sessao.post.return_value = mock.Mock(status_code=200, text="{}")

    def test_cria_a_tarefa_com_a_rota_o_segredo_e_os_parametros(self):
        importacao = self.criar()

        with self.captureOnCommitCallbacks(execute=True):
            services.agendar_leitura(importacao)

        url, = self.sessao.post.call_args.args
        self.assertEqual(url, "https://cloudtasks.googleapis.com/v2/projects/p/locations/l/queues/q/tasks")
        pedido = self.sessao.post.call_args.kwargs["json"]["task"]["appEngineHttpRequest"]
        self.assertEqual(pedido["httpMethod"], "POST")
        self.assertEqual(pedido["relativeUri"], "/importacao/tarefas/importacao.ler/")
        self.assertEqual(pedido["headers"]["X-Tarefas-Segredo"], SEGREDO)
        self.assertEqual(json.loads(base64.b64decode(pedido["body"])), {"importacao_id": importacao.pk})
        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PROCESSANDO)  # quem lê é a tarefa, depois

    def test_cloud_tasks_recusando_vira_falha(self):
        self.sessao.post.return_value = mock.Mock(status_code=403, text="Permission denied")
        importacao = self.criar()

        with self.assertLogs("importacao.tarefas", "ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                services.agendar_leitura(importacao)

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.FALHOU)

    @override_settings(TAREFAS_FILA="")
    def test_sem_fila_configurada_vira_falha(self):
        importacao = self.criar()

        with self.assertLogs("importacao.tarefas", "ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                services.agendar_leitura(importacao)

        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.FALHOU)
        self.sessao.post.assert_not_called()


class RotaDeTarefasTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        ambiente = mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": SEGREDO})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        self.url = reverse("importacao:tarefa", args=["importacao.ler"])

    def post(self, corpo, segredo=SEGREDO, url=None):
        cabecalhos = {"X-Tarefas-Segredo": segredo} if segredo is not None else {}
        return self.client.post(url or self.url, corpo, content_type="application/json", headers=cabecalhos)

    def test_segredo_certo_roda_a_tarefa(self):
        importacao = self.criar()
        services.guardar_arquivo(importacao, png(), "image/png")

        with mock.patch("importacao.services.chamar_ia", return_value=resposta(nome="Vendas")):
            resposta_http = self.post(json.dumps({"importacao_id": importacao.pk}))

        self.assertEqual(resposta_http.status_code, 200)
        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.PRONTA)

    def test_recusas(self):
        self.assertEqual(self.post("{}", segredo="errado").status_code, 403)
        self.assertEqual(self.post("{}", segredo=None).status_code, 403)
        self.assertEqual(self.post("[1]").status_code, 400)
        self.assertEqual(self.post("nao é json").status_code, 400)
        self.assertEqual(self.post("{}", url=reverse("importacao:tarefa", args=["nao.existe"])).status_code, 404)
        self.assertEqual(self.client.get(self.url, headers={"X-Tarefas-Segredo": SEGREDO}).status_code, 405)

    def test_sem_segredo_configurado_recusa_tudo(self):
        with mock.patch.dict(os.environ, {"TAREFAS_SEGREDO": ""}):
            self.assertEqual(self.post("{}", segredo="").status_code, 403)

    def test_parametros_errados_nao_derrubam_a_rota(self):
        with self.assertLogs("importacao.views", "ERROR"):
            self.assertEqual(self.post(json.dumps({"outro": 1})).status_code, 200)

    def test_app_engine_nao_redireciona_a_rota_de_tarefas(self):
        app_yaml = (Path(settings.BASE_DIR) / "app.yaml").read_text(encoding="utf-8")
        handler = app_yaml.index("- url: /importacao/tarefas/")
        geral = app_yaml.index("- url: /.*")

        self.assertLess(handler, geral)  # o primeiro handler que casa é o que vale
        self.assertRegex(app_yaml[handler:geral], r"secure:\s*optional")
        self.assertTrue(re.match(r"/importacao/tarefas/", self.url))
