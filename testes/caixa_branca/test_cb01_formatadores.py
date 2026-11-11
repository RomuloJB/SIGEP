from django.test import SimpleTestCase

from cadastros.masks import format_cnpj, format_cpf, format_phone


class FormatadoresDeMascaraTests(SimpleTestCase):
    """
    CB01 (TC-14): as duas saídas da decisão de tamanho em format_cpf,
    format_cnpj e format_phone (cadastros/masks.py). Com a quantidade de
    dígitos esperada aplica a máscara; com outra quantidade devolve o valor
    sem alteração.
    """

    def test_cpf_com_11_digitos_recebe_a_mascara(self):
        self.assertEqual(format_cpf("12345678901"), "123.456.789-01")

    def test_cpf_com_outro_tamanho_volta_sem_alteracao(self):
        self.assertEqual(format_cpf("1234"), "1234")

    def test_cnpj_com_e_sem_14_digitos(self):
        self.assertEqual(format_cnpj("12345678000199"), "12.345.678/0001-99")
        self.assertEqual(format_cnpj("123"), "123")

    def test_celular_com_11_digitos_e_valor_curto(self):
        self.assertEqual(format_phone("41999999999"), "(41) 99999-9999")
        self.assertEqual(format_phone("4199"), "4199")
