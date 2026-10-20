import re

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Company, User_Profile


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joao", "joao@exemplo.com", "SenhaAntiga@123")

    def _solicitar_link(self):
        response = self.client.post(reverse("password-reset"), {"email": "joao@exemplo.com"})
        self.assertRedirects(response, reverse("password-reset-done"))
        self.assertEqual(len(mail.outbox), 1)
        return re.search(r"https?://[^\s\"]+/reset/[^\s\"]+/", mail.outbox[0].body).group(0)

    def test_envia_email_com_link_em_texto_e_html(self):
        self._solicitar_link()
        email = mail.outbox[0]
        self.assertEqual(email.to, ["joao@exemplo.com"])
        self.assertEqual(email.subject, "SIGEP - Redefinição de senha")
        self.assertEqual(email.alternatives[0][1], "text/html")

    def test_email_inexistente_nao_envia_nem_revela(self):
        response = self.client.post(reverse("password-reset"), {"email": "ninguem@exemplo.com"})
        self.assertRedirects(response, reverse("password-reset-done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_link_redefine_senha_e_so_vale_uma_vez(self):
        link = self._solicitar_link()

        # O Django troca o token da URL por "set-password" e redireciona
        response = self.client.get(link, follow=True)
        self.assertTrue(response.context["validlink"])
        set_password_url = response.redirect_chain[-1][0]

        response = self.client.post(set_password_url, {
            "new_password1": "NovaSenha@456",
            "new_password2": "NovaSenha@456",
        })
        self.assertRedirects(response, reverse("password-reset-complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenha@456"))

        # Reutilizar o mesmo link deve cair na tela de link inválido
        self.client.logout()
        response = self.client.get(link, follow=True)
        self.assertFalse(response.context["validlink"])

    def test_login_exibe_link_esqueci_senha(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("password-reset"))


DADOS_PESSOAIS = {"name": "Maria Souza", "phone": "(44) 99999-9999", "cpf": "123.456.789-09"}


class SelectCompanyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gerente", "g@exemplo.com", "Senha@12345")
        self.client.force_login(self.user)

    def _empresa(self, nome):
        company = Company.objects.create(name=nome, cnpj="12345678000199", created_by=self.user)
        company.manager.add(self.user)
        return company

    def test_uma_empresa_ativa_direto_e_pula_a_selecao(self):
        company = self._empresa("Única")
        response = self.client.get(reverse("select-company"))
        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["active_company_id"], company.id)

    def test_mais_de_uma_empresa_mostra_a_selecao(self):
        self._empresa("A")
        self._empresa("B")
        response = self.client.get(reverse("select-company"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("active_company_id", self.client.session)

    def test_nenhuma_empresa_mostra_a_selecao_vazia(self):
        response = self.client.get(reverse("select-company"))
        self.assertContains(response, "Nenhuma empresa associada")

    def test_cabecalho_usa_o_apelido_da_empresa(self):
        company = self._empresa("Empresa de Nome Comprido Ltda")
        company.session_name = "Comprido"
        company.save()
        self.client.get(reverse("activate-company", args=[company.pk]))
        self.assertEqual(self.client.session["company_name"], "Comprido")


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@exemplo.com", "Senha@12345")
        self.comum = User.objects.create_user("comum", "comum@exemplo.com", "Senha@12345")

    def test_superusuario_cadastra_usuario_com_perfil(self):
        self.client.force_login(self.admin)
        manager = Group.objects.get_or_create(name="Manager")[0]
        response = self.client.post(reverse("user-create"), {
            "username": "novo", "email": "novo@exemplo.com", **DADOS_PESSOAIS,
            "password1": "OutraSenha@789", "password2": "OutraSenha@789",
            "is_active": "on", "groups": [manager.pk],
        })
        self.assertRedirects(response, reverse("user-list"))
        novo = User.objects.get(username="novo")
        self.assertTrue(novo.check_password("OutraSenha@789"))
        self.assertEqual(list(novo.groups.all()), [manager])
        self.assertEqual(novo.profile.cpf, "12345678909")

    def test_cadastro_rejeita_senha_fraca(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user-create"), {
            "username": "fraco", "email": "fraco@exemplo.com", **DADOS_PESSOAIS,
            "password1": "123", "password2": "123", "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="fraco").exists())

    def test_editar_usuario_cria_perfil_que_faltava(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user-update", args=[self.comum.pk]), {
            "username": "comum", "email": "comum@exemplo.com", **DADOS_PESSOAIS, "is_active": "on",
        })
        self.assertRedirects(response, reverse("user-list"))
        self.assertEqual(User_Profile.objects.get(user=self.comum).name, "Maria Souza")

    def test_usuario_comum_nao_acessa_gerenciamento(self):
        self.client.force_login(self.comum)
        for url in (reverse("user-list"), reverse("user-create"), reverse("user-update", args=[self.admin.pk])):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_rotas_antigas_de_perfil_nao_existem(self):
        self.client.force_login(self.comum)
        self.assertEqual(self.client.get("/userprofile/create/").status_code, 404)
        self.assertEqual(self.client.get("/userprofile/1/update/").status_code, 404)


class MyProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joao", "joao@exemplo.com", "SenhaAntiga@123")
        User.objects.create_user("outro", "outro@exemplo.com", "Senha@12345")
        self.client.force_login(self.user)

    def test_edita_os_proprios_dados(self):
        response = self.client.post(reverse("my-profile"), {"email": "novo@exemplo.com", **DADOS_PESSOAIS})
        self.assertRedirects(response, reverse("my-profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "novo@exemplo.com")
        self.assertEqual(self.user.profile.phone, "44999999999")

    def test_nao_aceita_email_de_outro_usuario(self):
        response = self.client.post(reverse("my-profile"), {"email": "OUTRO@exemplo.com", **DADOS_PESSOAIS})
        self.assertContains(response, "Este e-mail já está em uso")

    def test_troca_de_senha_mantem_logado(self):
        response = self.client.post(reverse("password-change"), {
            "old_password": "SenhaAntiga@123",
            "new_password1": "NovaSenha@456",
            "new_password2": "NovaSenha@456",
        })
        self.assertRedirects(response, reverse("my-profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenha@456"))
        self.assertEqual(self.client.get(reverse("my-profile")).status_code, 200)

    def test_menu_do_header_leva_ao_meu_perfil(self):
        response = self.client.get(reverse("my-profile"))
        self.assertContains(response, 'href="{}"'.format(reverse("my-profile")))
        self.assertNotContains(response, "Perfis de Usuários")


class RegisterTests(TestCase):
    def test_cadastro_publico_cria_usuario_e_perfil(self):
        response = self.client.post(reverse("register"), {
            "username": "publico", "email": "publico@exemplo.com", **DADOS_PESSOAIS,
            "password1": "OutraSenha@789", "password2": "OutraSenha@789",
        })
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="publico")
        self.assertTrue(user.check_password("OutraSenha@789"))
        self.assertEqual(user.profile.name, "Maria Souza")
        self.assertFalse(user.is_superuser)
