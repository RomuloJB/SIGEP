from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Company
from ia import cota, provedores
from ia.models import ConfiguracaoIA, ConfiguracaoIAUsuario, ConsumoIA, RequisicaoIA


class TelasIATestCase(TestCase):

    def setUp(self):
        cache.delete(ConfiguracaoIA.CHAVE_CACHE)
        provedores._cache.clear()
        config = ConfiguracaoIA.obter()
        config.provedor = ConfiguracaoIA.Provedor.FALSO
        config.save()

        self.comum = User.objects.create_user("comum", password="x")
        self.outro = User.objects.create_user("outro", password="x")
        self.admin = User.objects.create_superuser("admin", password="x")
        empresa = Company.objects.create(name="Empresa", cnpj="00000000000191", created_by=self.admin)

        self.minha = RequisicaoIA.objects.create(
            usuario=self.comum, finalidade="minha_finalidade", provedor="falso", situacao="sucesso",
            tokens_total=30, referencia=empresa,
        )
        RequisicaoIA.objects.create(
            usuario=self.outro, finalidade="finalidade_do_outro", provedor="falso", situacao="erro_permanente",
        )
        ConsumoIA.objects.create(usuario=self.comum, mes=cota.mes_atual(), tokens_total=30, requisicoes=1)

    def urls_de_administracao(self):
        return [
            reverse("ia:requisicao-list"),
            reverse("ia:requisicao-detail", args=[self.minha.pk]),
            reverse("ia:configuracao"),
            reverse("ia:usuario-list"),
            reverse("ia:usuario-update", args=[self.comum.pk]),
        ]

    def test_usuario_comum_recebe_403_nas_telas_de_administracao(self):
        self.client.force_login(self.comum)
        for url in self.urls_de_administracao():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in (reverse("ia:testar-conexao"), reverse("ia:usuario-padrao", args=[self.comum.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_usuario_comum_ve_so_o_proprio_consumo(self):
        self.client.force_login(self.comum)
        resposta = self.client.get(reverse("ia:meu-consumo"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "minha_finalidade")
        self.assertNotContains(resposta, "finalidade_do_outro")
        self.assertEqual(resposta.context["situacao"].usado, 30)
        # Sem custo em dólar para o usuário comum
        self.assertNotContains(resposta, "US$")
        # Menu: só o link de consumo, sem os de administração
        self.assertContains(resposta, reverse("ia:meu-consumo"))
        self.assertNotContains(resposta, reverse("ia:configuracao"))

    def test_anonimo_vai_para_o_login(self):
        login = reverse("login")
        for url in self.urls_de_administracao() + [reverse("ia:meu-consumo")]:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.url.startswith(login))

    def test_superusuario_abre_todas_as_telas(self):
        self.client.force_login(self.admin)
        for url in self.urls_de_administracao() + [reverse("ia:meu-consumo")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        configuracao = self.client.get(reverse("ia:configuracao"))
        for texto in ("As mudanças valem na próxima chamada, sem deploy.", "Modelo", "Limites padrão por usuário",
                      "Proteção do sistema", "Preços", "Testar conexão"):
            self.assertContains(configuracao, texto)

        lista = self.client.get(reverse("ia:requisicao-list"), {"situacao": "sucesso"})
        self.assertEqual(list(lista.context["requisicaoia_list"]), [self.minha])
        self.assertEqual(lista.context["resumo"]["maiores_referencias"][0]["tokens"], 30)

    def test_salvar_excecao_e_voltar_ao_padrao(self):
        self.client.force_login(self.admin)
        url = reverse("ia:usuario-update", args=[self.comum.pk])
        self.client.post(url, {"ia_habilitada": "on", "limite_mensal": "500000", "observacao": "teste"})
        self.assertEqual(cota.limite_do_usuario(self.comum), 500000)

        lista = self.client.get(reverse("ia:usuario-list"))
        self.assertContains(lista, "próprio: 500.000")

        self.client.post(reverse("ia:usuario-padrao", args=[self.comum.pk]))
        self.assertFalse(ConfiguracaoIAUsuario.objects.filter(usuario=self.comum).exists())
        self.assertEqual(cota.limite_do_usuario(self.comum), ConfiguracaoIA.obter().limite_mensal_usuario)

    def test_testar_conexao_mostra_resultado_em_mensagem(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("ia:testar-conexao"))

        self.assertRedirects(resposta, reverse("ia:configuracao"))
        mensagens = [str(m) for m in get_messages(resposta.wsgi_request)]
        self.assertTrue(any("Conexão funcionando" in m for m in mensagens), mensagens)
