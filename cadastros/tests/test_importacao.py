"""
Importador de pedidos (cadastros/importacao.py) sem IA: a leitura é uma instância do esquema
montada à mão. Só o fluxo completo simula a chamar_ia, como manda o contrato da importação.
"""
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from cadastros.importacao import (
    CLIENTE_NOVO, MSG_SAIU_DA_EMPRESA, MSG_SEM_EMPRESA, ImportadorPedido, ItemLido, PedidoLido,
)
from cadastros.models import Client, Company, Order, OrderStatus, Product
from ia.models import ConfiguracaoIA
from importacao import services as importacao_services
from importacao.importadores import REGISTRO, AjusteInvalido, ImportacaoInvalida, NaoReconhecido
from importacao.models import ConfiguracaoImportacao, Importacao
from importacao.tests.base import png

from .base import CadastrosTestCase

S = Importacao.Situacao


def lido(**campos):
    campos.setdefault("documento_reconhecido", True)
    return PedidoLido(**campos)


def item(**campos):
    return ItemLido(**campos)


class ImportadorPedidoTestCase(CadastrosTestCase):

    def setUp(self):
        super().setUp()
        self.importador = ImportadorPedido()
        self.escopo = {"empresa": self.empresa.pk}
        # Outra empresa, de que o rep1 não participa: nada dela pode aparecer nem ser escolhido
        self.outra = Company.objects.create(name="Empresa B", cnpj="11111111000191", created_by=self.gerente)
        self.cliente_da_outra = Client.objects.create(
            name="Cliente da B", cnpj_cpf="99999999999", uf="SP", company=self.outra, created_by=self.gerente,
        )
        self.produto_da_outra = Product.objects.create(
            name="Produto da B", sku="PB-1", unit_value=Decimal("5.00"), stock=5, company=self.outra, created_by=self.gerente,
        )

    def documento(self, **campos):
        """Um talão completo do Cliente Teste: 2 unidades do Produto Teste no boleto 30/60/90."""
        base = {
            "numero_documento": "123", "data_documento": "03/10/2026",
            "cliente_nome": "Cliente Teste", "cliente_documento": "000.000.000-00",
            "forma_pagamento": "boleto 30dias", "parcelas": "3",
            "entrega_endereco": "Rua das Flores, 120", "entrega_cidade": "Curitiba", "entrega_uf": "PR",
            "itens": [item(codigo="PT-1", descricao="Produto Teste", quantidade="2", valor_unitario="10,00")],
        }
        base.update(campos)
        return base

    def ler(self, usuario=None, **campos):
        return self.importador.normalizar(lido(**campos).model_dump(mode="json"), usuario or self.rep1, self.escopo)

    def confirmar(self, dados, usuario=None, dados_form=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.importador.confirmar(dados, usuario or self.rep1, self.escopo, dados_form)

    # ─── Documento completo ───────────────────────────────────────────────────

    def test_documento_completo_vira_pedido_pendente_com_estoque_baixado(self):
        dados, avisos = self.ler(**self.documento())

        self.assertEqual(avisos, [])
        self.assertEqual(dados["cliente_id"], self.cliente.pk)
        self.assertEqual((dados["payment_method"], dados["installments"]), ("boleto 30dias", 3))
        self.assertEqual((dados["address"], dados["city"], dados["uf"]), ("Rua das Flores, 120", "Curitiba", "PR"))
        self.assertEqual(dados["data_documento"], "2026-10-03")

        pedido = self.confirmar(dados)

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, OrderStatus.PENDENTE)
        self.assertEqual((pedido.type, pedido.company, pedido.created_by, pedido.client), ("OUT", self.empresa, self.rep1, self.cliente))
        self.assertEqual((pedido.payment_method, pedido.installments, pedido.uf), ("boleto 30dias", 3, "PR"))
        self.assertEqual(pedido.total_value, Decimal("20.00"))
        itens = list(pedido.product_orders.values_list("product_id", "quantity", "unit_value", "discount"))
        self.assertEqual(itens, [(self.produto.pk, 2, Decimal("10.00"), Decimal("0.00"))])
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 8)
        # Pendente: os gerentes são avisados, como no envio pela tela
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["gerente@sigep.test"])
        self.assertIn(reverse("order-detail", args=[pedido.pk]), mail.outbox[0].body)

    def test_resumo_mostra_empresa_cliente_itens_total_e_o_que_a_confirmacao_faz(self):
        dados, _ = self.ler(**self.documento())

        resumo = dict(self.importador.resumo(dados))

        self.assertEqual(resumo["Empresa"], "Empresa A")
        self.assertIn("Cliente Teste", resumo["Cliente"])
        self.assertEqual(resumo["Pagamento"], "Boleto(30) em 3x")
        self.assertIn("2 × PT-1 · Produto Teste", resumo["Itens (1)"])
        self.assertIn("20,00", resumo["Total"])
        self.assertIn("estoque é baixado", resumo["Ao confirmar"])

    # ─── Ids só das listas do contexto ────────────────────────────────────────

    def test_id_fora_da_lista_vira_vazio_com_aviso(self):
        dados, avisos = self.ler(
            cliente_nome="Cliente da B", cliente_id=self.cliente_da_outra.pk,
            itens=[item(descricao="Produto da B", quantidade="1", produto_id=self.produto_da_outra.pk)],
        )

        self.assertIsNone(dados["cliente_id"])
        self.assertIn("O cliente sugerido pela leitura não está na lista da empresa: foi ignorado.", avisos)
        self.assertEqual(dados["itens"], [])
        self.assertIn('O produto sugerido para "Produto da B" não está na lista da empresa: foi ignorado.', avisos)
        self.assertIn('Não encontrei "Produto da B" no cadastro de produtos: o item ficou fora do pedido.', avisos)

    def test_id_alem_do_limite_da_lista_tambem_nao_vale(self):
        zeta = Product.objects.create(name="Zeta", sku="ZT-1", unit_value=1, stock=1, company=self.empresa, created_by=self.gerente)

        with mock.patch("cadastros.importacao.LIMITE_LISTA", 1):
            dados, avisos = self.ler(**self.documento(itens=[item(descricao="Zeta", quantidade="1", produto_id=zeta.pk)]))

        self.assertEqual(dados["itens"], [])
        self.assertIn('O produto sugerido para "Zeta" não está na lista da empresa: foi ignorado.', avisos)

    def test_sku_lido_vale_mais_que_a_sugestao_e_acha_produto_fora_da_lista(self):
        zeta = Product.objects.create(name="Zeta", sku="ZT-1", unit_value=1, stock=1, company=self.empresa, created_by=self.gerente)

        with mock.patch("cadastros.importacao.LIMITE_LISTA", 1):
            dados, _ = self.ler(**self.documento(itens=[item(codigo=" zt-1 ", quantidade="1", produto_id=self.produto.pk)]))

        self.assertEqual([linha["produto_id"] for linha in dados["itens"]], [zeta.pk])

    def test_produto_que_nao_esta_no_cadastro_fica_fora_e_o_resto_continua(self):
        dados, avisos = self.ler(**self.documento(itens=[
            item(codigo="PT-1", quantidade="1"),
            item(codigo="XYZ-9", descricao="Caneta azul", quantidade="5"),
        ]))

        self.assertEqual([linha["produto_id"] for linha in dados["itens"]], [self.produto.pk])
        self.assertIn('Não encontrei "Caneta azul" no cadastro de produtos: o item ficou fora do pedido.', avisos)

    def test_linhas_repetidas_do_mesmo_produto_viram_uma_so(self):
        dados, avisos = self.ler(**self.documento(itens=[
            item(codigo="PT-1", quantidade="2"), item(descricao="Produto Teste", quantidade="3", produto_id=self.produto.pk),
        ]))

        self.assertEqual([(linha["produto_id"], linha["quantidade"]) for linha in dados["itens"]], [(self.produto.pk, 5)])
        self.assertIn('"Produto Teste" aparece em mais de uma linha do documento: juntei as quantidades.', avisos)

    # ─── Datas e valores como texto ───────────────────────────────────────────

    def test_data_ilegivel_fica_vazia(self):
        for texto in ("31/02/2026", "3 de outubro", "??/10/2026", None):
            with self.subTest(texto=texto):
                dados, _ = self.ler(**self.documento(data_documento=texto))
                self.assertEqual(dados["data_documento"], "")

    def test_quantidade_ilegivel_fica_vazia_e_a_confirmacao_aponta_o_item(self):
        dados, avisos = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="dois")]))

        self.assertIsNone(dados["itens"][0]["quantidade"])
        self.assertIn('Não li a quantidade de "Produto Teste": corrija a quantidade e o desconto em 🌐 Editar no site.', avisos)
        with self.assertRaises(ImportacaoInvalida) as erro:
            self.confirmar(dados)
        self.assertIn("Quantidade · PT-1 · Produto Teste", " ".join(erro.exception.erros["__all__"]))
        self.assertFalse(Order.objects.exists())

    def test_preco_do_documento_menor_vira_desconto_e_percentual_vira_reais(self):
        # Cadastro: R$ 10,00. Documento: 2 × R$ 8,00 com 10% → desconto 2 × 2,00 + 10% de 16,00
        dados, avisos = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="2", valor_unitario="8,00", desconto="10%")]))

        self.assertEqual(dados["itens"][0]["desconto"], "5.60")
        self.assertTrue(any("é menor que o do cadastro" in aviso and "virou desconto" in aviso for aviso in avisos))
        pedido = self.confirmar(dados)
        self.assertEqual(pedido.total_value, Decimal("14.40"))
        self.assertEqual(pedido.product_orders.get().discount, Decimal("5.60"))

    def test_preco_do_documento_maior_mantem_o_do_cadastro(self):
        dados, avisos = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="2", valor_unitario="R$ 12,50")]))

        self.assertEqual(dados["itens"][0]["desconto"], "0.00")
        self.assertTrue(any("é maior que o do cadastro" in aviso and "vale o do cadastro" in aviso for aviso in avisos))

    def test_desconto_em_reais_e_desconto_que_passa_do_item(self):
        em_reais, _ = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="2", desconto="R$ 3,00")]))
        demais, avisos = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="2", desconto="50,00")]))

        self.assertEqual(em_reais["itens"][0]["desconto"], "3.00")
        self.assertEqual(demais["itens"][0]["desconto"], "0")
        self.assertTrue(any("passa do valor do item" in aviso for aviso in avisos))

    def test_parcelas_so_valem_no_boleto(self):
        pix, _ = self.ler(**self.documento(forma_pagamento="pix", parcelas="3"))
        sem_forma, avisos = self.ler(**self.documento(forma_pagamento=None))

        self.assertEqual((pix["payment_method"], pix["installments"]), ("pix", 1))
        self.assertEqual(sem_forma["payment_method"], "")
        self.assertIn("Não li a forma de pagamento: toque em ✏️ Pagamento.", avisos)

    def test_sem_endereco_de_entrega_a_uf_fica_para_a_pessoa(self):
        dados, avisos = self.ler(**self.documento(entrega_endereco=None, entrega_cidade=None, entrega_uf=None))

        self.assertEqual(dados["uf"], "")
        self.assertIn("O documento não traz a UF de entrega: toque em ✏️ UF de entrega.", avisos)
        with self.assertRaises(ImportacaoInvalida) as erro:
            self.confirmar(dados)
        self.assertIn("uf", erro.exception.erros)  # o bot aponta ✏️ UF de entrega

    # ─── Documento não reconhecido ────────────────────────────────────────────

    def test_documento_nao_reconhecido(self):
        with self.assertRaisesMessage(NaoReconhecido, "É uma nota fiscal, não um pedido."):
            self.ler(documento_reconhecido=False, motivo_nao_reconhecido="É uma nota fiscal, não um pedido.")
        with self.assertRaisesMessage(NaoReconhecido, "Não parece um pedido de venda."):
            self.ler(documento_reconhecido=False)

    # ─── Cliente: reaproveitar o existente ou cadastrar o novo ────────────────

    def test_cliente_existente_e_reaproveitado_pelo_cnpj_cpf_mesmo_com_outra_sugestao(self):
        parecido = Client.objects.create(name="Cliente Teste Filial", cnpj_cpf="22222222222", uf="PR", company=self.empresa, created_by=self.gerente)

        dados, _ = self.ler(**self.documento(cliente_id=parecido.pk))
        pedido = self.confirmar(dados)

        self.assertEqual(pedido.client, self.cliente)
        self.assertEqual(Client.objects.filter(company=self.empresa).count(), 2)

    def test_cliente_existente_e_reaproveitado_pela_sugestao_quando_nao_ha_cnpj_cpf(self):
        dados, _ = self.ler(**self.documento(cliente_documento=None, cliente_id=self.cliente.pk))

        self.assertEqual(self.confirmar(dados).client, self.cliente)

    def test_cliente_novo_e_cadastrado_com_os_dados_do_documento(self):
        dados, avisos = self.ler(**self.documento(
            cliente_nome="Papelaria Nova", cliente_documento="11.222.333/0001-81", cliente_endereco="Av. Brasil, 500",
            cliente_cidade="Ponta Grossa", cliente_uf="pr",
        ))

        self.assertIsNone(dados["cliente_id"])
        self.assertIn("O cliente não está cadastrado: ele será cadastrado ao confirmar.", avisos)
        cliente = self.confirmar(dados).client
        self.assertEqual(
            (cliente.name, cliente.cnpj_cpf, cliente.address, cliente.city, cliente.uf, cliente.company, cliente.created_by),
            ("Papelaria Nova", "11222333000181", "Av. Brasil, 500", "Ponta Grossa", "PR", self.empresa, self.rep1),
        )

    def test_cliente_novo_sem_os_obrigatorios_pede_os_campos_e_nada_e_gravado(self):
        dados, avisos = self.ler(**self.documento(cliente_nome="Papelaria Nova", cliente_documento=None))

        self.assertIn("✏️ CNPJ/CPF do cliente, ✏️ UF do cliente novo", " ".join(avisos))
        with self.assertRaises(ImportacaoInvalida) as erro:
            self.confirmar(dados)
        self.assertEqual(set(erro.exception.erros), {"cdoc", "cuf"})  # os códigos dos botões do bot
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Client.objects.filter(company=self.empresa).count(), 1)

        dados, _ = self.importador.ajustar(dados, "cdoc", "11.222.333/0001-81", self.rep1, self.escopo)
        dados, _ = self.importador.ajustar(dados, "cuf", "SC", self.rep1, self.escopo)
        self.assertEqual(self.confirmar(dados).client.cnpj_cpf, "11222333000181")

    def test_cnpj_cpf_ja_cadastrado_nao_cria_cliente_repetido(self):
        dados, _ = self.ler(**self.documento(cliente_documento=None, cliente_uf="PR"))
        dados["cliente_novo"]["cnpj_cpf"] = self.cliente.cnpj_cpf  # ex.: digitado no site

        with self.assertRaises(ImportacaoInvalida) as erro:
            self.confirmar(dados)
        self.assertIn("já tem este CNPJ/CPF", " ".join(erro.exception.erros["cdoc"]))

    # ─── Estoque ──────────────────────────────────────────────────────────────

    def test_sem_estoque_a_confirmacao_falha_e_nada_muda(self):
        dados, _ = self.ler(**self.documento(itens=[item(codigo="PT-1", quantidade="50")]))

        with self.assertRaises(ImportacaoInvalida) as erro:
            self.confirmar(dados)

        self.assertIn("Estoque insuficiente para 'Produto Teste': disponível 10, solicitado 50.", erro.exception.erros["__all__"])
        self.assertFalse(Order.objects.exists())
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.stock, 10)
        self.assertEqual(len(mail.outbox), 0)

    # ─── Escopo (empresa) ─────────────────────────────────────────────────────

    def test_escopo_precisa_de_uma_empresa_da_pessoa(self):
        self.assertEqual(self.importador.conferir_escopo(self.rep1, {}), MSG_SEM_EMPRESA)
        self.assertEqual(self.importador.conferir_escopo(self.rep1, {"empresa": self.outra.pk}), MSG_SAIU_DA_EMPRESA)
        self.assertEqual(self.importador.conferir_escopo(self.rep1, self.escopo), "")

    def test_contexto_leva_so_a_empresa_do_escopo_sem_dados_sensiveis(self):
        texto = self.importador.contexto(self.rep1, self.escopo)

        self.assertIn("{} · Cliente Teste · PR".format(self.cliente.pk), texto)
        self.assertIn("{} · PT-1 · Produto Teste · UND".format(self.produto.pk), texto)
        for proibido in ("00000000000", "000.000.000-00", "gerente@sigep.test", "10.00", "10,00", "Cliente da B", "PB-1"):
            self.assertNotIn(proibido, texto)

    def test_opcoes_de_cliente_sao_da_empresa_com_a_opcao_de_cliente_novo(self):
        opcoes = self.importador.opcoes_de_cliente(self.rep1, self.escopo)

        self.assertEqual(opcoes[0][0], CLIENTE_NOVO)
        self.assertEqual([nome for _, nome in opcoes[1:]], ["Cliente Teste"])
        self.assertEqual(self.importador.opcoes_de_cliente(self.rep1, {"empresa": self.outra.pk}), [])

    # ─── Correções pelo bot ───────────────────────────────────────────────────

    def test_ajustes_do_bot(self):
        dados, _ = self.ler(**self.documento(entrega_uf=None))

        dados, mensagem = self.importador.ajustar(dados, "cli", CLIENTE_NOVO, self.rep1, self.escopo)
        self.assertIsNone(dados["cliente_id"])
        dados, mensagem = self.importador.ajustar(dados, "cdoc", "000.000.000-00", self.rep1, self.escopo)
        self.assertEqual(dados["cliente_id"], self.cliente.pk)
        self.assertIn("Encontrei o cliente Cliente Teste", mensagem)
        with self.assertRaisesMessage(AjusteInvalido, "Para cadastrar outro, escolha ➕ Cliente novo"):
            self.importador.ajustar(dados, "cuf", "SP", self.rep1, self.escopo)
        with self.assertRaises(AjusteInvalido):
            self.importador.ajustar(dados, "uf", "XX", self.rep1, self.escopo)
        with self.assertRaises(AjusteInvalido):
            self.importador.ajustar(dados, "cli", self.cliente_da_outra.pk, self.rep1, self.escopo)
        dados, _ = self.importador.ajustar(dados, "uf", "sc", self.rep1, self.escopo)
        dados, _ = self.importador.ajustar(dados, "pag", "pix", self.rep1, self.escopo)

        self.assertEqual((dados["uf"], dados["payment_method"], dados["installments"]), ("SC", "pix", 1))
        self.assertEqual(self.confirmar(dados).uf, "SC")


@override_settings(TAREFAS_BACKEND="imediata")
class ImportacaoDePedidoTestCase(CadastrosTestCase):
    """O importador no fluxo da importação: IA simulada, pelo services e pela tela Revisar."""

    def setUp(self):
        super().setUp()
        for chave in (ConfiguracaoIA.CHAVE_CACHE, ConfiguracaoImportacao.CHAVE_CACHE):
            cache.delete(chave)
        registro = mock.patch.dict(REGISTRO, {ImportadorPedido.tipo: ImportadorPedido()}, clear=True)
        registro.start()
        self.addCleanup(registro.stop)
        self.leitura = lido(
            cliente_nome="Cliente Teste", cliente_documento="000.000.000-00", forma_pagamento="pix", entrega_uf="PR",
            itens=[item(codigo="PT-1", descricao="Produto Teste", quantidade="2")],
        )
        patch = mock.patch("importacao.services.chamar_ia", return_value=mock.Mock(dados=self.leitura))
        self.chamar_ia = patch.start()
        self.addCleanup(patch.stop)

    def test_do_arquivo_ao_pedido_pelo_services(self):
        importacao = importacao_services.iniciar_importacao(
            self.rep1, Importacao.Origem.TELEGRAM, escopo={"empresa": self.empresa.pk}, arquivo_mime="image/png",
        )
        importacao_services.processar_importacao(importacao, png(), "image/png")
        importacao.refresh_from_db()

        self.assertEqual(importacao.situacao, S.PRONTA)
        pedido_ia = self.chamar_ia.call_args.kwargs["montar_pedido"](ConfiguracaoIA.obter())
        self.assertIn("Empresa que vende (não é o cliente): Empresa A", pedido_ia.texto)
        self.assertNotIn("00000000000", pedido_ia.texto)
        self.assertEqual(pedido_ia.esquema, ImportadorPedido.esquema)

        with self.captureOnCommitCallbacks(execute=True):
            importacao_services.confirmar_importacao(importacao, self.rep1, "telegram")
        importacao.refresh_from_db()
        self.assertEqual(importacao.situacao, S.CONFIRMADA)
        self.assertEqual(importacao.objeto.status, OrderStatus.PENDENTE)

    def test_sem_empresa_no_escopo_a_importacao_e_recusada(self):
        with self.assertRaisesMessage(importacao_services.ImportacaoRecusada, MSG_SEM_EMPRESA):
            importacao_services.iniciar_importacao(self.rep1, Importacao.Origem.SITE)

    def test_tela_revisar_corrige_itens_e_cliente_e_confirma(self):
        escopo = {"empresa": self.empresa.pk}
        dados, avisos = ImportadorPedido().normalizar(self.leitura.model_dump(mode="json"), self.rep1, escopo)
        importacao = Importacao.objects.create(
            criado_por=self.rep1, tipo=ImportadorPedido.tipo, situacao=S.PRONTA, escopo=escopo, dados=dados, avisos=avisos,
        )
        self.entrar(self.rep1)
        url = reverse("importacao:revisar", args=[importacao.pk])

        tela = self.client.get(url)
        self.assertContains(tela, "Quantidade · PT-1 · Produto Teste")
        self.assertContains(tela, "Estoque agora: 10")

        envio = {
            "client": "", "cliente_nome": "Papelaria Nova", "cliente_cnpj_cpf": "11.222.333/0001-81", "cliente_uf": "SC",
            "cliente_endereco": "", "cliente_cidade": "", "payment_method": "pix", "installments": "1",
            "address": "", "city": "", "uf": "PR", "item_0_quantidade": "3", "item_0_desconto": "1.50",
        }
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(url, envio)

        self.assertRedirects(resposta, reverse("importacao:detalhe", args=[importacao.pk]))
        pedido = Order.objects.get()
        self.assertEqual(pedido.client.name, "Papelaria Nova")
        self.assertEqual(pedido.product_orders.get().quantity, 3)
        self.assertEqual(pedido.total_value, Decimal("28.50"))
        detalhe = self.client.get(reverse("importacao:detalhe", args=[importacao.pk]))
        self.assertContains(detalhe, reverse("order-detail", args=[pedido.pk]))
