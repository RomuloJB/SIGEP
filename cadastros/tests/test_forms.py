from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from cadastros.forms import CPFCNPJField, PhoneField


class CPFCNPJFieldTestCase(SimpleTestCase):

    def test_cpf_com_mascara_volta_so_os_digitos(self):
        self.assertEqual(CPFCNPJField().clean("123.456.789-01"), "12345678901")

    def test_cnpj_com_mascara_volta_so_os_digitos(self):
        self.assertEqual(CPFCNPJField().clean("12.345.678/0001-99"), "12345678000199")

    def test_doze_digitos_e_invalido(self):
        with self.assertRaises(ValidationError) as erro:
            CPFCNPJField().clean("123456789012")

        self.assertEqual(erro.exception.code, "invalid")


class PhoneFieldTestCase(SimpleTestCase):

    def test_telefone_obrigatorio_vazio(self):
        with self.assertRaises(ValidationError) as erro:
            PhoneField(required=True).clean("")

        self.assertEqual(erro.exception.code, "required")
