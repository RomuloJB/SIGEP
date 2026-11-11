import re
import unicodedata

from django.test import SimpleTestCase
from django.urls import reverse

from cadastros.estados import UF
from cadastros.filters import ClientFilter
from cadastros.forms import ClientForm
from cadastros.importacao import UFS
from cadastros.models import Client

from .base import CadastrosTestCase


def sem_acento(nome):
    return unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().casefold()


class EnumEstadosTestCase(SimpleTestCase):

    def test_os_27_estados_com_sigla_de_2_letras(self):
        self.assertEqual(len(UF.choices), 27)
        self.assertEqual(len(set(UF.values)), 27)
        for sigla in UF.values:
            with self.subTest(sigla=sigla):
                self.assertRegex(sigla, r"^[A-Z]{2}$")

    def test_ordem_alfabetica_pelo_nome(self):
        nomes = list(UF.labels)
        self.assertEqual(nomes, sorted(nomes, key=sem_acento))
        # Os casos em que a ordem pelo nome difere da ordem pela sigla
        self.assertLess(nomes.index("Amapá"), nomes.index("Amazonas"))
        self.assertLess(nomes.index("Pará"), nomes.index("Paraíba"))
        self.assertLess(nomes.index("Paraíba"), nomes.index("Paraná"))
        self.assertLess(nomes.index("Santa Catarina"), nomes.index("São Paulo"))

    def test_importador_usa_as_mesmas_siglas(self):
        self.assertEqual(UFS, frozenset(UF.values))


class UFDoClienteTestCase(CadastrosTestCase):

    def dados(self, **campos):
        return {"name": "Papelaria Central", "cnpj_cpf": "123.456.789-09", "address": "", "city": "", "uf": "PR", **campos}

    def test_dropdown_mostra_os_nomes_em_ordem_alfabetica(self):
        opcoes = ClientForm().fields["uf"].choices
        self.assertEqual(opcoes[0][0], "")  # a opção vazia vira o "Busque o estado…"
        self.assertEqual(opcoes[1:], UF.choices)

    def test_dropdown_tem_busca_e_7_opcoes_visiveis(self):
        html = str(ClientForm()["uf"])
        self.assertIn("data-tom-select", html)
        self.assertIn('data-opcoes-visiveis="7"', html)
        self.assertIn("data-buscar-pelo-valor", html)
        self.assertIn('<option value="PR">Paraná</option>', html)

    def test_grava_a_sigla_e_recusa_o_que_nao_e_estado(self):
        self.assertTrue(ClientForm(data=self.dados(uf="SC")).is_valid())
        for invalida in ("XX", "pr", "Paraná", ""):
            with self.subTest(uf=invalida):
                self.assertIn("uf", ClientForm(data=self.dados(uf=invalida)).errors)

    def test_cadastro_pela_tela_grava_a_sigla_e_mostra_o_nome(self):
        self.entrar(self.rep1)
        tela = self.client.get(reverse("client-create")).content.decode()
        self.assertIn("tom-select.complete.min.js", tela)
        self.assertIn("js/select-search.js", tela)

        resposta = self.client.post(reverse("client-create"), self.dados(uf="MS"))
        cliente = Client.objects.get(name="Papelaria Central")
        self.assertRedirects(resposta, reverse("client-detail", args=[cliente.pk]))
        self.assertEqual((cliente.uf, cliente.get_uf_display()), ("MS", "Mato Grosso do Sul"))

    def test_edicao_abre_com_o_estado_do_cliente_escolhido(self):
        self.entrar(self.gerente)
        tela = self.client.get(reverse("client-update", args=[self.cliente.pk])).content.decode()
        self.assertRegex(tela, r'<option value="PR" selected>Paraná</option>')

    def test_filtro_da_lista_e_um_dropdown_de_estados(self):
        filtro = ClientFilter(data={"uf": "PR"}, queryset=Client.objects.all())
        self.assertEqual(list(filtro.qs), [self.cliente])
        self.assertEqual(list(filtro.form.fields["uf"].choices)[1:], UF.choices)
        self.assertFalse(re.search(r'name="uf"[^>]*type="text"', str(filtro.form["uf"])))
