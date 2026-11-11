from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from telegram.entradas import (
    DICA_DATA, DICA_NUMERO, DICA_QUANTIDADE, DICA_TERMO, DICA_VALOR, EntradaInvalida, interpretar_data,
    interpretar_numero, interpretar_quantidade, interpretar_termo, interpretar_valor,
)

HOJE = date(2026, 11, 7)


class EntradasTestCase(SimpleTestCase):

    def conferir(self, funcao, casos, **kwargs):
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(funcao(texto, **kwargs), esperado)

    def recusar(self, funcao, textos, dica, **kwargs):
        for texto in textos:
            with self.subTest(texto=texto):
                with self.assertRaisesMessage(EntradaInvalida, dica):
                    funcao(texto, **kwargs)

    def test_datas(self):
        self.conferir(interpretar_data, {
            "hoje": HOJE,
            "Hoje": HOJE,
            " ontem ": date(2026, 11, 6),
            "anteontem": date(2026, 11, 5),
            "amanhã": date(2026, 11, 8),
            "amanha": date(2026, 11, 8),
            "03/10": date(2026, 10, 3),
            "3/10": date(2026, 10, 3),
            "3/10/26": date(2026, 10, 3),
            "03/10/2026": date(2026, 10, 3),
            "31/12/1999": date(1999, 12, 31),
            "2026-10-03": date(2026, 10, 3),
            "29/02/2028": date(2028, 2, 29),
        }, hoje=HOJE)

    def test_datas_invalidas(self):
        self.recusar(interpretar_data, [
            "", "depois", "31/02/2026", "29/02/2026", "00/10", "10/13", "3-10-2026", "03/10/226", "2026/10/03",
            "32/01", "3 de outubro",
        ], DICA_DATA, hoje=HOJE)

    def test_data_sem_hoje_usa_a_data_local(self):
        self.assertIsInstance(interpretar_data("hoje"), date)

    def test_valores(self):
        self.conferir(interpretar_valor, {
            "1.234,56": Decimal("1234.56"),
            "R$ 50": Decimal("50.00"),
            "r$50": Decimal("50.00"),
            "R$ 1.234,5": Decimal("1234.50"),
            "50,5": Decimal("50.50"),
            "50.5": Decimal("50.50"),
            "50.50": Decimal("50.50"),
            "0,99": Decimal("0.99"),
            "1234": Decimal("1234.00"),
            "1.234": Decimal("1234.00"),
            "1.234.567,89": Decimal("1234567.89"),
            "0": Decimal("0.00"),
        })

    def test_valores_invalidos(self):
        self.recusar(interpretar_valor, [
            "", "abc", "-5", "50,555", "1,234.56", "12.34.5", "1.23,4", ",50", "R$", "5 reais", "1.2345",
        ], DICA_VALOR)

    def test_quantidades(self):
        self.conferir(interpretar_quantidade, {
            "3": 3, " 3 ": 3, "3x": 3, "3X": 3, "3 x": 3, "3 parcelas": 3, "1 parcela": 1, "12 vezes": 12,
            "5 un": 5, "2 unidades": 2,
        })

    def test_quantidades_invalidas(self):
        self.recusar(interpretar_quantidade, ["", "0", "0x", "-1", "2,5", "três", "x3", "1234567890"], DICA_QUANTIDADE)

    def test_numeros(self):
        self.conferir(interpretar_numero, {
            "128": 128, "#128": 128, "# 128": 128, "nº 128": 128, "Nº128": 128, "n° 128": 128, "no 128": 128,
            "pedido 128": 128, "Pedido nº 128": 128,
        })

    def test_numeros_invalidos(self):
        self.recusar(interpretar_numero, ["", "0", "abc", "12a", "-3", "pedido", "1.234", "1234567890"], DICA_NUMERO)

    def test_termos(self):
        self.conferir(interpretar_termo, {
            "caderno": "caderno",
            "  caneta   azul ": "caneta azul",
            "ab": "ab",
            "123": "123",
            "CAD-096": "CAD-096",
            "ç" * 2: "çç",
            "x" * 30: "x" * 30,
        })

    def test_termos_invalidos(self):
        self.recusar(interpretar_termo, ["", "a", "12", "a1", "--", "  ", "x" * 31], DICA_TERMO)
