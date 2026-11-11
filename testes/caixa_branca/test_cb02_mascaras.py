from django.test import SimpleTestCase

from cadastros.masks import format_cpf_cnpj


class FormatCpfCnpjTestCase(SimpleTestCase):

    def test_cpf_com_11_digitos(self):
        self.assertEqual(format_cpf_cnpj("123.456.789-01"), "123.456.789-01")

    def test_cnpj_com_14_digitos(self):
        self.assertEqual(format_cpf_cnpj("12345678000199"), "12.345.678/0001-99")

    def test_valor_com_outro_tamanho_volta_sem_alteracao(self):
        self.assertEqual(format_cpf_cnpj("12345"), "12345")
