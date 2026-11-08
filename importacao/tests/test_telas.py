from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from ia.models import ConfiguracaoIA, ConfiguracaoIAUsuario
from importacao.importadores import REGISTRO
from importacao.models import Importacao

from .base import TIPO, ImportacaoTestCase, OutroImportador, png, resposta

S = Importacao.Situacao


def arquivo(conteudo=None, nome="nota.png", mime="image/png"):
    return SimpleUploadedFile(nome, png() if conteudo is None else conteudo, content_type=mime)


class TelasTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)
        patch = mock.patch("importacao.services.chamar_ia", return_value=resposta(nome="Equipe de vendas"))
        self.chamar_ia = patch.start()
        self.addCleanup(patch.stop)

    def enviar(self, **dados):
        dados.setdefault("arquivo", arquivo())
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("importacao:nova"), dados)

    # ─── Lista ────────────────────────────────────────────────────────────────

    def test_lista_so_as_importacoes_da_pessoa_com_filtro(self):
        minha_pronta = self.criar(situacao=S.PRONTA, arquivo_nome="minha-pronta.pdf")
        self.criar(situacao=S.FALHOU, arquivo_nome="minha-falha.pdf")
        self.criar(usuario=self.bia, situacao=S.PRONTA, arquivo_nome="da-bia.pdf")

        resposta_http = self.client.get(reverse("importacao:lista"))
        self.assertContains(resposta_http, "minha-pronta.pdf")
        self.assertContains(resposta_http, "minha-falha.pdf")
        self.assertNotContains(resposta_http, "da-bia.pdf")

        filtrada = self.client.get(reverse("importacao:lista"), {"situacao": "pronta"})
        self.assertEqual(list(filtrada.context["importacao_list"]), [minha_pronta])

    def test_sem_importadores_avisa_e_esconde_o_botao(self):
        with mock.patch.dict(REGISTRO, {}, clear=True):
            resposta_http = self.client.get(reverse("importacao:lista"))

        self.assertContains(resposta_http, "Ainda não há nenhum tipo de documento")
        self.assertNotContains(resposta_http, reverse("importacao:nova"))

    def test_pede_login(self):
        self.client.logout()

        resposta_http = self.client.get(reverse("importacao:lista"))

        self.assertEqual(resposta_http.status_code, 302)
        self.assertIn(reverse("login"), resposta_http.url)

    # ─── Nova importação ──────────────────────────────────────────────────────

    def test_enviar_le_e_mostra_o_detalhe(self):
        resposta_http = self.enviar(observacao="cupom")

        importacao = Importacao.objects.get()
        self.assertRedirects(resposta_http, reverse("importacao:detalhe", args=[importacao.pk]))
        self.assertEqual(importacao.situacao, S.PRONTA)  # fila "imediata": leu logo depois do commit
        self.assertEqual((importacao.origem, importacao.arquivo_nome, importacao.observacao), ("site", "nota.png", "cupom"))
        self.assertEqual(self.chamar_ia.call_args.kwargs["origem"], "site")

    def test_arquivo_grande_e_recusado_antes_de_ler(self):
        config = ConfiguracaoIA.obter()
        config.tamanho_maximo_mb = 1
        config.save()

        resposta_http = self.enviar(arquivo=arquivo(b"0" * (1024 * 1024 + 1), nome="grande.pdf", mime="application/pdf"))

        self.assertEqual(resposta_http.status_code, 200)
        self.assertContains(resposta_http, "o máximo é 1 MB")
        self.assertFalse(Importacao.objects.exists())
        self.chamar_ia.assert_not_called()

    def test_recusa_do_servico_aparece_no_form(self):
        ConfiguracaoIAUsuario.objects.create(usuario=self.ana, ia_habilitada=False)

        resposta_http = self.enviar()

        self.assertContains(resposta_http, "A leitura por IA está desligada para a sua conta.")
        self.assertFalse(Importacao.objects.exists())

    def test_com_varios_tipos_a_pessoa_escolhe(self):
        with mock.patch.dict(REGISTRO, {"teste.outro": OutroImportador()}):
            self.assertContains(self.client.get(reverse("importacao:nova")), "Outro documento")
            sem_tipo = self.enviar()
            self.assertEqual(sem_tipo.status_code, 200)
            self.assertFalse(Importacao.objects.exists())

            self.enviar(tipo="teste.outro", arquivo=arquivo())

        self.assertEqual(Importacao.objects.get().tipo, "teste.outro")

    # ─── Detalhe e ações ──────────────────────────────────────────────────────

    def test_importacao_de_outra_pessoa_da_404(self):
        da_bia = self.criar(usuario=self.bia, situacao=S.PRONTA, dados={"nome": "x"})

        for rota in ("detalhe", "revisar"):
            self.assertEqual(self.client.get(reverse("importacao:" + rota, args=[da_bia.pk])).status_code, 404)
        for rota in ("revisar", "descartar", "tentar-de-novo", "escolher-tipo"):
            self.assertEqual(self.client.post(reverse("importacao:" + rota, args=[da_bia.pk])).status_code, 404)
        da_bia.refresh_from_db()
        self.assertEqual(da_bia.situacao, S.PRONTA)

    def test_detalhe_lendo_se_atualiza_sozinho(self):
        lendo = self.criar()
        pronta = self.criar(situacao=S.PRONTA, dados={"nome": "Equipe", "itens": []}, avisos=["Confira o nome."])

        self.assertContains(self.client.get(reverse("importacao:detalhe", args=[lendo.pk])), "location.reload")
        detalhe = self.client.get(reverse("importacao:detalhe", args=[pronta.pk]))
        self.assertNotContains(detalhe, "location.reload")
        self.assertContains(detalhe, "Confira o nome.")
        self.assertContains(detalhe, reverse("importacao:revisar", args=[pronta.pk]))

    def test_detalhe_abre_em_todas_as_situacoes(self):
        grupo = Group.objects.create(name="Criado na confirmação")
        for situacao in S.values:
            with self.subTest(situacao=situacao):
                importacao = self.criar(situacao=situacao, tipo="" if situacao == S.AGUARDANDO_TIPO else TIPO,
                                        dados={"nome": "Equipe", "itens": []}, mensagem_erro="Motivo da falha.")
                if situacao == S.CONFIRMADA:
                    importacao.objeto = grupo
                    importacao.save()
                resposta_http = self.client.get(reverse("importacao:detalhe", args=[importacao.pk]))
                self.assertEqual(resposta_http.status_code, 200)
                self.assertEqual("tentar-de-novo" in resposta_http.content.decode(), importacao.pode_tentar_de_novo)
                self.assertEqual("/tipo/" in resposta_http.content.decode(), situacao == S.AGUARDANDO_TIPO)

    def test_revisar_mostra_o_form_do_app_preenchido(self):
        pronta = self.criar(situacao=S.PRONTA, dados={"nome": "Equipe de vendas", "itens": []}, avisos=["Confira o nome."])

        resposta_http = self.client.get(reverse("importacao:revisar", args=[pronta.pk]))

        self.assertContains(resposta_http, 'value="Equipe de vendas"')
        self.assertContains(resposta_http, "Confira o nome.")

    def test_confirmar_pelo_site_cria_o_registro(self):
        pronta = self.criar(situacao=S.PRONTA, dados={"nome": "Equipe de vendas", "itens": []})

        resposta_http = self.client.post(reverse("importacao:revisar", args=[pronta.pk]), {"nome": "Equipe corrigida"})

        self.assertRedirects(resposta_http, reverse("importacao:detalhe", args=[pronta.pk]))
        pronta.refresh_from_db()
        self.assertEqual(pronta.situacao, S.CONFIRMADA)
        self.assertEqual(pronta.objeto, Group.objects.get(name="Equipe corrigida"))

    def test_form_invalido_volta_com_o_erro(self):
        pronta = self.criar(situacao=S.PRONTA, dados={"nome": "Equipe", "itens": []})
        grupos = Group.objects.count()

        resposta_http = self.client.post(reverse("importacao:revisar", args=[pronta.pk]), {"nome": ""})

        self.assertEqual(resposta_http.status_code, 200)
        self.assertTrue(resposta_http.context["form"].errors)
        pronta.refresh_from_db()
        self.assertEqual(pronta.situacao, S.PRONTA)
        self.assertEqual(Group.objects.count(), grupos)

    def test_revisar_o_que_nao_esta_pronto_volta_para_o_detalhe(self):
        confirmada = self.criar(situacao=S.CONFIRMADA)

        resposta_http = self.client.get(reverse("importacao:revisar", args=[confirmada.pk]))

        self.assertRedirects(resposta_http, reverse("importacao:detalhe", args=[confirmada.pk]))

    def test_descartar(self):
        pronta = self.criar(situacao=S.PRONTA)

        self.client.post(reverse("importacao:descartar", args=[pronta.pk]))

        pronta.refresh_from_db()
        self.assertEqual(pronta.situacao, S.DESCARTADA)

    def test_tentar_de_novo_pede_o_arquivo(self):
        falhou = self.criar(situacao=S.FALHOU, mensagem_erro="Não consegui ler agora.")
        url = reverse("importacao:tentar-de-novo", args=[falhou.pk])

        self.client.post(url)  # sem arquivo
        falhou.refresh_from_db()
        self.assertEqual(falhou.situacao, S.FALHOU)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"arquivo": arquivo()})
        falhou.refresh_from_db()
        self.assertEqual(falhou.situacao, S.PRONTA)
        self.assertEqual(falhou.tentativas, 1)

    def test_escolher_tipo_pelo_site(self):
        aguardando = self.criar(situacao=S.AGUARDANDO_TIPO, tipo="")
        from importacao import services
        services.guardar_arquivo(aguardando, png(), "image/png")

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("importacao:escolher-tipo", args=[aguardando.pk]), {"tipo": TIPO})

        aguardando.refresh_from_db()
        self.assertEqual((aguardando.tipo, aguardando.situacao), (TIPO, S.PRONTA))

    # ─── Menu e configuração ──────────────────────────────────────────────────

    def test_menu_mostra_quantas_estao_para_revisar(self):
        self.criar(situacao=S.PRONTA)
        self.criar(situacao=S.PRONTA)
        self.criar(usuario=self.bia, situacao=S.PRONTA)

        resposta_http = self.client.get(reverse("importacao:lista"))

        self.assertContains(resposta_http, 'class="app-sidebar__emblema" title="2 para revisar"')

    def test_menu_sem_nada_para_revisar_nao_mostra_emblema(self):
        self.assertNotContains(self.client.get(reverse("importacao:lista")), "app-sidebar__emblema")

    def test_configuracao_so_para_superusuario(self):
        with self.assertLogs("django.request", "WARNING"):  # o 403 esperado não suja a saída
            self.assertEqual(self.client.get(reverse("importacao:configuracao")).status_code, 403)

        self.client.force_login(User.objects.create_superuser("root", password="x"))
        self.assertEqual(self.client.get(reverse("importacao:configuracao")).status_code, 200)
