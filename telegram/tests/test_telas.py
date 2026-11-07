from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from telegram.models import ConfiguracaoTelegram, LimiteTelegram, MensagemTelegram, VinculoTelegram

BLOQUEADA = 9_000_000_001
LIVRE = 9_000_000_002


class TelasTelegramTestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoTelegram.CHAVE_CACHE)
        self.admin = User.objects.create_superuser("admin", password="x")
        self.comum = User.objects.create_user("comum", password="x")
        self.entrada = MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.ENTRADA, tipo="comando", usuario=self.comum, telegram_id=BLOQUEADA,
            texto="/start ***", conteudo={"update_id": 1, "message": {"text": "/start ***"}},
            situacao=MensagemTelegram.Situacao.PROCESSADA, update_id=1,
        )
        self.saida = MensagemTelegram.objects.create(
            direcao=MensagemTelegram.Direcao.SAIDA, metodo_api="sendMessage", texto="resposta do bot",
            situacao=MensagemTelegram.Situacao.FALHOU, erro="Forbidden: bot was blocked",
        )
        self.bloqueada = LimiteTelegram.objects.create(
            telegram_id=BLOQUEADA, mensagens=21, total=30, descartadas=9, janela_inicio=timezone.now(),
            bloqueado_ate=timezone.now() + timedelta(minutes=5),
        )
        self.livre = LimiteTelegram.objects.create(telegram_id=LIVRE, total=3)
        VinculoTelegram.objects.create(usuario=self.comum, telegram_id=BLOQUEADA, chat_id=BLOQUEADA, nome="Ana Souza")

    def urls(self):
        return [
            reverse("telegram:mensagem-list"),
            reverse("telegram:mensagem-detail", args=[self.entrada.pk]),
            reverse("telegram:remetente-list"),
            reverse("telegram:configuracao"),
        ]

    def test_usuario_comum_recebe_403(self):
        self.client.force_login(self.comum)

        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        resposta = self.client.post(reverse("telegram:remetente-liberar", args=[self.bloqueada.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.bloqueada.refresh_from_db()
        self.assertTrue(self.bloqueada.bloqueado)

    def test_anonimo_vai_para_o_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.url.startswith(reverse("login")))

    def test_superusuario_abre_as_telas_e_ve_o_menu(self):
        self.client.force_login(self.admin)

        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        resposta = self.client.get(reverse("telegram:conexao"))
        for rota in ("telegram:mensagem-list", "telegram:remetente-list", "telegram:configuracao"):
            self.assertContains(resposta, 'href="{}"'.format(reverse(rota)))

    def test_menu_de_quem_nao_e_superusuario_nao_tem_as_telas(self):
        self.client.force_login(self.comum)

        resposta = self.client.get(reverse("telegram:conexao"))

        self.assertNotContains(resposta, reverse("telegram:mensagem-list"))
        self.assertNotContains(resposta, reverse("telegram:configuracao"))

    # Log

    def listar_log(self, **filtros):
        self.client.force_login(self.admin)
        return list(self.client.get(reverse("telegram:mensagem-list"), filtros).context["object_list"])

    def test_log_sem_filtro_mostra_tudo_do_mais_novo_ao_mais_antigo(self):
        self.assertEqual(self.listar_log(), [self.saida, self.entrada])

    def test_filtros_do_log(self):
        self.assertEqual(self.listar_log(usuario="com"), [self.entrada])
        self.assertEqual(self.listar_log(direcao="saida"), [self.saida])
        self.assertEqual(self.listar_log(situacao="falhou"), [self.saida])

    def test_filtro_de_periodo_inclui_o_ultimo_dia(self):
        hoje = timezone.localdate().isoformat()
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()

        self.assertEqual(len(self.listar_log(criado_em_min=hoje, criado_em_max=hoje)), 2)
        self.assertEqual(self.listar_log(criado_em_max=ontem), [])

    def test_detalhe_mostra_o_json(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:mensagem-detail", args=[self.entrada.pk]))

        self.assertContains(resposta, "&quot;update_id&quot;: 1")
        self.assertContains(resposta, "/start ***")

    def test_detalhe_sem_json_explica_o_motivo_e_mostra_o_erro(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:mensagem-detail", args=[self.saida.pk]))

        self.assertContains(resposta, "Sem JSON")
        self.assertContains(resposta, "Forbidden: bot was blocked")

    def test_detalhe_de_saida_nao_escreve_none_nos_ids_vazios(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:mensagem-detail", args=[self.saida.pk]))

        self.assertContains(resposta, "<th>Id do update</th><td>—</td>", html=True)
        self.assertNotContains(resposta, "None")

    def test_detalhe_mostra_os_ids_sem_separador_de_milhar(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:mensagem-detail", args=[self.entrada.pk]))

        self.assertContains(resposta, "<td>{}</td>".format(BLOQUEADA), html=True)

    # Remetentes

    def listar_remetentes(self, **filtros):
        self.client.force_login(self.admin)
        return self.client.get(reverse("telegram:remetente-list"), filtros)

    def test_remetentes_mostra_contadores_e_quem_esta_conectado(self):
        resposta = self.listar_remetentes()

        self.assertContains(resposta, "comum")
        self.assertContains(resposta, "Ana Souza")
        self.assertContains(resposta, "Não conectado")
        self.assertContains(resposta, "Bloqueado até")

    def test_liberar_so_aparece_para_quem_esta_bloqueado(self):
        resposta = self.listar_remetentes()

        self.assertContains(resposta, reverse("telegram:remetente-liberar", args=[self.bloqueada.pk]))
        self.assertNotContains(resposta, reverse("telegram:remetente-liberar", args=[self.livre.pk]))

    def test_filtros_de_remetentes(self):
        bloqueados = self.listar_remetentes(bloqueio="bloqueado").context["object_list"]
        livres = self.listar_remetentes(bloqueio="livre").context["object_list"]
        por_usuario = self.listar_remetentes(usuario="comu").context["object_list"]

        self.assertEqual(list(bloqueados), [self.bloqueada])
        self.assertEqual(list(livres), [self.livre])
        self.assertEqual(list(por_usuario), [self.bloqueada])

    def test_bloqueio_vencido_conta_como_livre(self):
        LimiteTelegram.objects.filter(pk=self.bloqueada.pk).update(bloqueado_ate=timezone.now() - timedelta(seconds=1))

        self.assertEqual(self.listar_remetentes(bloqueio="bloqueado").context["object_list"].count(), 0)

    def test_liberar_encerra_o_bloqueio(self):
        self.client.force_login(self.admin)

        resposta = self.client.post(reverse("telegram:remetente-liberar", args=[self.bloqueada.pk]))

        self.assertRedirects(resposta, reverse("telegram:remetente-list"))
        self.assertEqual(str(list(get_messages(resposta.wsgi_request))[0]), "Remetente liberado.")
        self.bloqueada.refresh_from_db()
        self.assertFalse(self.bloqueada.bloqueado)

    def test_liberar_nao_aceita_get(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:remetente-liberar", args=[self.bloqueada.pk]))

        self.assertEqual(resposta.status_code, 405)
        self.bloqueada.refresh_from_db()
        self.assertTrue(self.bloqueada.bloqueado)

    # Configuração

    def dados_da_configuracao(self, **alterados):
        return {
            "mensagens_por_minuto": 20, "arquivos_por_minuto": 4, "bloqueio_minutos": 5,
            "desconhecido_mensagens_por_minuto": 5, "desconhecido_bloqueio_minutos": 60,
            "desconhecido_aviso_horas": 12, "espera_minutos": 15, "reter_conteudo_dias": 30,
            "reter_mensagens_dias": 60, **alterados,
        }

    def test_configuracao_explica_cada_numero(self):
        self.client.force_login(self.admin)

        resposta = self.client.get(reverse("telegram:configuracao"))

        for campo in resposta.context["form"].fields.values():
            self.assertTrue(campo.help_text)
            self.assertContains(resposta, campo.help_text.replace('"', "&quot;"))

    def test_salvar_a_configuracao_vale_na_hora(self):
        self.client.force_login(self.admin)
        self.assertEqual(ConfiguracaoTelegram.obter().mensagens_por_minuto, 20)  # deixa no cache

        resposta = self.client.post(reverse("telegram:configuracao"), self.dados_da_configuracao(mensagens_por_minuto=7))

        self.assertRedirects(resposta, reverse("telegram:configuracao"))
        self.assertEqual(ConfiguracaoTelegram.obter().mensagens_por_minuto, 7)
        self.assertEqual(ConfiguracaoTelegram.objects.count(), 1)

    def test_configuracao_recusa_zero(self):
        self.client.force_login(self.admin)

        resposta = self.client.post(reverse("telegram:configuracao"), self.dados_da_configuracao(bloqueio_minutos=0))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("bloqueio_minutos", resposta.context["form"].errors)
