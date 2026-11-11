"""
Importador de pedidos de venda: a foto ou o PDF de um pedido vira um rascunho de Order.

Documentos: talão de pedido preenchido à mão pelo representante, pedido de compra do cliente
(PDF ou impresso) e print de pedido mandado por WhatsApp ou e-mail. O pedido é sempre de venda
(OUT) e, ao confirmar, já vai para aprovação (Pendente): o estoque é conferido e baixado e os
gerentes são avisados, pelas mesmas funções da tela de cadastro (cadastros/services.py).

- Empresa: vem do escopo da importação ({"empresa": id}) e é conferida a cada passo.
- Cliente: achado pelo CNPJ/CPF lido (no Python, nunca pela IA) ou pela sugestão da IA na lista.
  Se nenhum servir, a confirmação cadastra o cliente com os dados do documento; o que faltar a
  pessoa preenche (✏️ no bot ou na tela Revisar).
- Itens: o produto é achado pelo SKU lido ou pela sugestão da IA; o que não está no cadastro
  fica fora do pedido. O preço é o do cadastro: se o documento for mais barato, a diferença vira
  desconto do item. Desconto em % vira reais.
- Endereço de entrega: só o que o documento marca como entrega; sem ele, a UF fica para a pessoa.
"""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import pydantic
from django.conf import settings
from django.db import transaction
from django.db.models.functions import Lower, Trim
from django.utils.formats import number_format

from importacao.importadores import (
    REGRA_DE_SEGURANCA, AjusteInvalido, Campo, ImportacaoInvalida, Importador, NaoReconhecido, registrar,
)

from . import consultas, pedidos, services
from .estados import UF
from .forms import PedidoImportadoForm
from .masks import format_cpf_cnpj, only_digits
from .models import MAX_PARCELAS, METODOS_BOLETO, Client, PaymentMethod, Product

LIMITE_LISTA = 200  # opções de cada lista no contexto da IA
AVISOS_DA_IA = 5
CLIENTE_NOVO = 0  # opção "Cliente novo" do campo Cliente
UFS = frozenset(UF.values)
CENTAVOS = Decimal("0.01")

MSG_SEM_EMPRESA = "Escolha a empresa antes de importar."
MSG_SAIU_DA_EMPRESA = "Você não tem mais acesso à empresa desta importação."
MSG_CLIENTE_CADASTRADO = (
    "O pedido está com o cliente cadastrado {}. Para cadastrar outro, escolha ➕ Cliente novo em ✏️ Cliente."
)
DICA_UF = "Digite a sigla do estado, com 2 letras. Exemplo: PR"
DICA_DOCUMENTO = "Digite um CPF (000.000.000-00) ou um CNPJ (00.000.000/0000-00)."

Confianca = Literal["alta", "media", "baixa"]
FormaDePagamento = Literal[tuple(PaymentMethod.values)]


# ─── Esquema: o que a IA devolve ──────────────────────────────────────────────

class ItemLido(pydantic.BaseModel):
    codigo: str | None = None
    descricao: str | None = None
    quantidade: str | None = None
    valor_unitario: str | None = None
    desconto: str | None = None
    produto_id: int | None = None


class PedidoLido(pydantic.BaseModel):
    documento_reconhecido: bool
    motivo_nao_reconhecido: str | None = None
    numero_documento: str | None = None
    data_documento: str | None = None
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    cliente_endereco: str | None = None
    cliente_cidade: str | None = None
    cliente_uf: str | None = None
    cliente_id: int | None = None
    confianca_cliente: Confianca | None = None
    forma_pagamento: FormaDePagamento | None = None
    parcelas: str | None = None
    confianca_pagamento: Confianca | None = None
    entrega_endereco: str | None = None
    entrega_cidade: str | None = None
    entrega_uf: str | None = None
    itens: list[ItemLido] = []
    confianca_itens: Confianca | None = None
    avisos: list[str] = []


INSTRUCOES = """Você lê pedidos de venda de uma distribuidora para cadastrar no sistema SIGEP. O documento pode ser um talão de pedido preenchido à mão pelo representante, um pedido de compra do cliente (PDF ou papel impresso) ou o print de um pedido mandado por WhatsApp ou e-mail.

1. Se o documento não for um pedido de venda (ex.: nota fiscal, boleto, recibo, orçamento, foto sem documento), responda documento_reconhecido = false e explique o motivo em uma frase curta em motivo_nao_reconhecido.
2. O cliente é quem compra; a empresa que vende está no contexto e nunca é o cliente. Copie o nome ou a razão social do cliente, o CNPJ ou CPF dele (ex.: "12.345.678/0001-90"), o endereço, a cidade e a UF como estão no documento. UF é sempre a sigla com 2 letras (ex.: "Paraná" vira "PR").
3. cliente_id: o id da lista "Clientes cadastrados" que é o mesmo cliente do documento (mesmo nome, ou um nome fantasia que corresponde à razão social, na mesma cidade). Use SOMENTE ids da lista; se nenhum servir, null.
4. forma_pagamento: dinheiro ("à vista", "dinheiro"), pix, boleto 30dias, boleto 15dias, boleto 7dias, credito (cartão de crédito), debido (cartão de débito) ou crediario. Exemplos: "boleto 30/60/90" é boleto 30dias com parcelas "3"; "boleto 15 dias" é boleto 15dias; "cartão" sem dizer qual é null. Se não estiver escrita, null.
5. parcelas: só no boleto, quantos boletos, como texto (ex.: "3"). "30/60/90" são 3 parcelas.
6. entrega_endereco, entrega_cidade e entrega_uf: só se o documento marcar um endereço de entrega ("entregar em", "local de entrega"). O endereço do cliente não é o endereço de entrega: nesse caso, null.
7. itens: uma linha por produto pedido, na ordem do documento. codigo é o código ou SKU como escrito (ex.: "CAD-096-AZ"); descricao é o nome do produto como escrito; quantidade é o número de unidades pedidas, como texto (ex.: "12"); valor_unitario é o preço de uma unidade escrito no documento (ex.: "19,90"); desconto é o desconto da linha inteira, com "%" quando for percentual (ex.: "10%" ou "R$ 5,00"). Linhas de subtotal, total ou frete não são itens.
8. produto_id: o id da lista "Produtos cadastrados" do mesmo produto (SKU igual ou nome equivalente, ex.: "cad univ 96f" é "Caderno universitário 96 folhas"). Use SOMENTE ids da lista; se nenhum servir, null.
9. numero_documento e data_documento: o número do pedido ou do talão e a data, como escritos (ex.: "1234" e "03/10/2026").
10. Nunca invente data, valor, quantidade, CNPJ ou CPF: o que estiver ilegível, cortado ou ausente fica null. Copie os números exatamente como estão.
11. confianca_cliente, confianca_pagamento e confianca_itens: alta (legível e claro), media (deu para ler, com alguma dúvida) ou baixa (rasurado, cortado ou adivinhado).
12. avisos: até 5 frases curtas sobre o que a pessoa deve conferir (ex.: "A quantidade do 3º item está rasurada.").

""" + REGRA_DE_SEGURANCA


# ─── Conversões do texto lido (as mesmas regras de telegram/entradas.py) ──────

VALOR_BR = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")  # 1.234,56 · 1234,5 · 50 · 1.234
VALOR_PONTO = re.compile(r"^(\d+)\.(\d{1,2})$")  # 50.5 · 50.50
INTEIRO = re.compile(r"^\s*(\d{1,6})(?:[.,]0+)?\s*[^\d]*$")  # 12 · 12 un · 3x · 12,0
DATA_BR = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$")
DATA_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def _texto(texto, limite):
    """Texto lido, sem espaços sobrando e cortado no tamanho do campo do model."""
    return " ".join((texto or "").split())[:limite]


def _valor(texto):
    """1.234,56 · R$ 50 · 50,5 · 50.5 → Decimal, ou None se não der para entender."""
    limpo = (texto or "").strip().lower().replace(" ", "").removeprefix("r$")
    ponto = VALOR_PONTO.match(limpo)
    if ponto:
        return Decimal("{}.{}".format(ponto[1], ponto[2])).quantize(CENTAVOS)
    br = VALOR_BR.match(limpo)
    if not br:
        return None
    return Decimal("{}.{}".format(br[1].replace(".", ""), br[2] or "0")).quantize(CENTAVOS)


def _inteiro(texto):
    casou = INTEIRO.match(texto or "")
    return int(casou[1]) if casou else None


def _uf(texto):
    sigla = (texto or "").strip().upper()
    return sigla if sigla in UFS else ""


def _data(texto):
    """dd/mm/aaaa, dd/mm/aa ou aaaa-mm-dd → "aaaa-mm-dd"; data ilegível ou que não existe → ""."""
    limpo = (texto or "").strip()
    iso, br = DATA_ISO.match(limpo), DATA_BR.match(limpo)
    if iso:
        ano, mes, dia = (int(parte) for parte in iso.groups())
    elif br:
        dia, mes, ano = int(br[1]), int(br[2]), int(br[3]) + (2000 if len(br[3]) == 2 else 0)
    else:
        return ""
    try:
        return date(ano, mes, dia).isoformat()
    except ValueError:
        return ""


def _reais(valor):
    return "R$ " + number_format(Decimal(valor), 2, force_grouping=True)


def _forma(codigo):
    # Os rótulos do site são numerados ("3 - Boleto(30)"); aqui fica só o nome
    return re.sub(r"^\d+ - ", "", PaymentMethod(codigo).label) if codigo in PaymentMethod.values else ""


# ─── Importador ───────────────────────────────────────────────────────────────

@registrar
class ImportadorPedido(Importador):
    tipo = "cadastros.pedido"
    nome = "Pedido de venda"
    esquema = PedidoLido
    # Sem esquema_sem_itens: um pedido sem itens não pode ser confirmado ("Adicione pelo menos
    # um produto"), então um documento longo demais termina em "Não consegui ler".
    instrucoes = INSTRUCOES
    versao_prompt = "2026-11.1"
    form_class = PedidoImportadoForm

    # Campo do PedidoImportadoForm -> código do campo no bot (para o bot apontar o botão certo)
    CAMPOS_DO_FORM = {
        "client": "cli", "cliente_nome": "cnome", "cliente_cnpj_cpf": "cdoc", "cliente_uf": "cuf",
        "payment_method": "pag", "uf": "uf",
    }

    # ── Escopo ──

    def _empresa(self, usuario, escopo):
        """A empresa do escopo, se a pessoa ainda estiver nela."""
        empresa_id = (escopo or {}).get("empresa")
        if not str(empresa_id or "").isdigit():
            return None
        return consultas.empresas_do_usuario(usuario).filter(pk=int(empresa_id)).first()

    def conferir_escopo(self, usuario, escopo):
        if not (escopo or {}).get("empresa"):
            return MSG_SEM_EMPRESA
        return "" if self._empresa(usuario, escopo) else MSG_SAIU_DA_EMPRESA

    def _empresa_ou_recusa(self, usuario, escopo, erro):
        empresa = self._empresa(usuario, escopo)
        if empresa is None:
            raise erro(self.conferir_escopo(usuario, escopo))
        return empresa

    # ── Contexto: só o necessário (sem CPF/CNPJ, e-mail, preço ou estoque) ──

    @staticmethod
    def _clientes(empresa):
        return Client.objects.filter(company=empresa).order_by("name", "pk")

    @staticmethod
    def _produtos(empresa):
        return Product.objects.filter(company=empresa).order_by("name", "pk")

    @staticmethod
    def _ids_enviados(queryset):
        """Os ids que foram para a IA: os primeiros LIMITE_LISTA da lista, na mesma ordem do contexto."""
        return set(queryset.values_list("pk", flat=True)[:LIMITE_LISTA])

    @staticmethod
    def _lista(titulo, queryset, linha):
        registros = list(queryset[:LIMITE_LISTA + 1])
        linhas = [" ".join(linha(registro).split()) for registro in registros[:LIMITE_LISTA]]
        if len(registros) > LIMITE_LISTA:
            titulo += " — os primeiros {} em ordem de nome".format(LIMITE_LISTA)
        return "{}:\n{}".format(titulo, "\n".join(linhas) or "(nenhum)")

    def contexto(self, usuario, escopo):
        empresa = self._empresa(usuario, escopo)
        if empresa is None:
            return ""

        def cliente(registro):
            local = "/".join(parte for parte in (registro.city, registro.uf) if parte)
            return "{} · {} · {}".format(registro.pk, registro.name, local or "-")

        def produto(registro):
            return "{} · {} · {} · {}".format(registro.pk, registro.sku, registro.name, registro.measure_unit)

        return "\n\n".join([
            "Empresa que vende (não é o cliente): {}".format(empresa.name),
            self._lista("Clientes cadastrados (id · nome · cidade/UF)", self._clientes(empresa), cliente),
            self._lista("Produtos cadastrados (id · SKU · nome · unidade)", self._produtos(empresa), produto),
        ])

    # ── Normalizar: a leitura vira o rascunho ──

    def normalizar(self, extracao, usuario, escopo):
        lido = self.esquema.model_validate(extracao)
        if not lido.documento_reconhecido:
            raise NaoReconhecido(_texto(lido.motivo_nao_reconhecido, 200) or "Não parece um pedido de venda.")
        empresa = self._empresa_ou_recusa(usuario, escopo, NaoReconhecido)

        avisos = []
        dados = {"empresa_id": empresa.pk, "empresa_nome": empresa.display_name}
        dados.update(self._cliente_lido(lido, empresa, avisos))
        dados.update(self._pagamento_lido(lido, avisos))
        dados.update(self._entrega_lida(lido, avisos))
        dados["itens"] = self._itens_lidos(lido, empresa, avisos)
        dados["numero_documento"] = _texto(lido.numero_documento, 30)
        dados["data_documento"] = _data(lido.data_documento)

        for confianca, o_que in ((lido.confianca_cliente, "o cliente"), (lido.confianca_pagamento, "o pagamento"),
                                 (lido.confianca_itens, "os itens")):
            if confianca in ("media", "baixa"):
                avisos.append("A leitura de {} ficou com {} confiança: confira.".format(
                    o_que, "pouca" if confianca == "baixa" else "média"))
        avisos += [aviso for aviso in (_texto(aviso, 200) for aviso in lido.avisos[:AVISOS_DA_IA]) if aviso]
        return dados, avisos

    def _cliente_lido(self, lido, empresa, avisos):
        novo = {
            "nome": _texto(lido.cliente_nome, 100),
            "cnpj_cpf": "",
            "endereco": _texto(lido.cliente_endereco, 100),
            "cidade": _texto(lido.cliente_cidade, 100),
            "uf": _uf(lido.cliente_uf),
        }
        digitos = only_digits(lido.cliente_documento or "")
        if digitos and len(digitos) not in (11, 14):
            avisos.append("O CNPJ/CPF do cliente no documento ({}) está incompleto.".format(_texto(lido.cliente_documento, 30)))
            digitos = ""
        novo["cnpj_cpf"] = digitos

        sugerido = None
        if lido.cliente_id is not None:
            if lido.cliente_id in self._ids_enviados(self._clientes(empresa)):
                sugerido = Client.objects.filter(company=empresa, pk=lido.cliente_id).first()
            else:
                avisos.append("O cliente sugerido pela leitura não está na lista da empresa: foi ignorado.")

        # O CNPJ/CPF do documento vale mais que a sugestão pelo nome
        pelo_documento = list(self._clientes(empresa).filter(cnpj_cpf=digitos)[:2]) if digitos else []
        if len(pelo_documento) == 1:
            cliente = pelo_documento[0]
        elif len(pelo_documento) > 1:
            cliente = sugerido if sugerido in pelo_documento else None
            if cliente is None:
                avisos.append("Há mais de um cliente com o CNPJ/CPF {}: escolha em ✏️ Cliente.".format(format_cpf_cnpj(digitos)))
        elif digitos:
            cliente = None  # CNPJ/CPF que ninguém tem: é um cliente novo
            if sugerido:
                avisos.append('O CNPJ/CPF {} não está cadastrado, mas o nome parece com "{}". Se for ele, escolha em ✏️ Cliente.'.format(
                    format_cpf_cnpj(digitos), sugerido.name))
        else:
            cliente = sugerido

        if cliente is None:
            avisos.append(self._aviso_cliente_novo(novo))
        return {"cliente_id": cliente.pk if cliente else None, "cliente_rotulo": str(cliente) if cliente else "",
                "cliente_novo": novo}

    @staticmethod
    def _aviso_cliente_novo(novo):
        faltando = [
            botao for chave, botao in (("nome", "✏️ Nome do cliente novo"), ("cnpj_cpf", "✏️ CNPJ/CPF do cliente"),
                                       ("uf", "✏️ UF do cliente novo"))
            if not novo.get(chave)
        ]
        texto = "O cliente não está cadastrado: ele será cadastrado ao confirmar."
        if faltando:
            texto += " Falta no documento: toque em {}.".format(", ".join(faltando))
        return texto

    @staticmethod
    def _pagamento_lido(lido, avisos):
        forma = lido.forma_pagamento or ""
        if not forma:
            avisos.append("Não li a forma de pagamento: toque em ✏️ Pagamento.")
        parcelas = 1
        if forma in METODOS_BOLETO and lido.parcelas:
            lidas = _inteiro(lido.parcelas)
            if lidas and 1 <= lidas <= MAX_PARCELAS:
                parcelas = lidas
            else:
                avisos.append('Não entendi as parcelas ("{}"): ficou 1. Corrija em 🌐 Editar no site, se for outro número.'.format(
                    _texto(lido.parcelas, 20)))
        return {"payment_method": forma, "installments": parcelas}

    @staticmethod
    def _entrega_lida(lido, avisos):
        uf = _uf(lido.entrega_uf)
        if not uf:
            avisos.append("O documento não traz a UF de entrega: toque em ✏️ UF de entrega.")
        return {"address": _texto(lido.entrega_endereco, 255), "city": _texto(lido.entrega_cidade, 100), "uf": uf}

    def _itens_lidos(self, lido, empresa, avisos):
        produtos = self._produtos(empresa)
        enviados = self._ids_enviados(produtos)
        codigos = {(item.codigo or "").strip().lower() for item in lido.itens} - {""}
        por_sku = {}
        if codigos:
            for produto in produtos.annotate(sku_lido=Lower(Trim("sku"))).filter(sku_lido__in=codigos):
                por_sku.setdefault(produto.sku_lido, []).append(produto)
        sugeridos = produtos.filter(pk__in=[item.produto_id for item in lido.itens if item.produto_id in enviados]).in_bulk()

        linhas = {}
        for item in lido.itens:
            nome = _texto(item.descricao, 100) or _texto(item.codigo, 30) or "item sem descrição"
            produto = self._produto_do_item(item, nome, por_sku, sugeridos, enviados, avisos)
            if produto is None:
                avisos.append('Não encontrei "{}" no cadastro de produtos: o item ficou fora do pedido.'.format(nome))
                continue
            quantidade = _inteiro(item.quantidade)
            if not quantidade:
                quantidade = None
                avisos.append('Não li a quantidade de "{}": corrija a quantidade e o desconto em 🌐 Editar no site.'.format(produto.name))
            desconto = self._desconto_do_item(item, produto, quantidade, avisos)

            atual = linhas.get(produto.pk)
            if atual is None:
                linhas[produto.pk] = {
                    "produto_id": produto.pk, "rotulo": "{} · {}".format(produto.sku, produto.name),
                    "preco": str(produto.unit_value), "quantidade": quantidade, "desconto": str(desconto),
                }
                continue
            # O formulário não aceita o mesmo produto duas vezes: as linhas viram uma só
            avisos.append('"{}" aparece em mais de uma linha do documento: juntei as quantidades.'.format(produto.name))
            atual["quantidade"] = atual["quantidade"] + quantidade if atual["quantidade"] and quantidade else None
            atual["desconto"] = str(Decimal(atual["desconto"]) + desconto)

        if not lido.itens:
            avisos.append("Não encontrei itens no documento.")
        elif not linhas:
            avisos.append("Nenhum item do documento está no cadastro de produtos: o pedido não pode ser confirmado.")
        return list(linhas.values())

    @staticmethod
    def _produto_do_item(item, nome, por_sku, sugeridos, enviados, avisos):
        """O SKU lido vale mais que a sugestão da IA; a sugestão só vale se o id estava na lista enviada."""
        candidatos = por_sku.get((item.codigo or "").strip().lower(), [])
        if len(candidatos) == 1:
            return candidatos[0]
        if item.produto_id is not None and item.produto_id not in enviados:
            avisos.append('O produto sugerido para "{}" não está na lista da empresa: foi ignorado.'.format(nome))
        sugerido = sugeridos.get(item.produto_id)
        if candidatos:  # mais de um produto com o mesmo SKU
            return sugerido if sugerido in candidatos else None
        return sugerido

    @staticmethod
    def _desconto_do_item(item, produto, quantidade, avisos):
        """
        O valor unitário é o do cadastro. Documento mais barato: a diferença vira desconto do item.
        Documento mais caro: vale o do cadastro. Desconto em % vira reais, sobre o preço do documento.
        """
        preco = produto.unit_value
        if quantidade is None:
            return Decimal("0")
        base, desconto = preco, Decimal("0")

        preco_documento = _valor(item.valor_unitario)
        if preco_documento is not None and preco_documento < preco:
            base = preco_documento
            desconto += (preco - preco_documento) * quantidade
            avisos.append('O preço de "{}" no documento ({}) é menor que o do cadastro ({}): a diferença virou desconto.'.format(
                produto.name, _reais(preco_documento), _reais(preco)))
        elif preco_documento is not None and preco_documento > preco:
            avisos.append('O preço de "{}" no documento ({}) é maior que o do cadastro ({}): vale o do cadastro.'.format(
                produto.name, _reais(preco_documento), _reais(preco)))

        texto = (item.desconto or "").strip()
        if texto:
            percentual = "%" in texto
            lido = _valor(texto.replace("%", ""))
            if lido is None or (percentual and lido > 100):
                avisos.append('Não entendi o desconto de "{}" ("{}"): ele ficou de fora.'.format(produto.name, _texto(texto, 20)))
            else:
                desconto += base * quantidade * lido / 100 if percentual else lido

        desconto = desconto.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        if desconto > preco * quantidade:
            avisos.append('O desconto de "{}" ({}) passa do valor do item: ele ficou de fora. Confira em 🌐 Editar no site.'.format(
                produto.name, _reais(desconto)))
            return Decimal("0")
        return desconto

    # ── Campos que o bot corrige ──

    def opcoes_de_cliente(self, usuario, escopo):
        empresa = self._empresa(usuario, escopo)
        if empresa is None:
            return []
        return [(CLIENTE_NOVO, "➕ Cliente novo (dados do documento)")] + [
            (cliente.pk, cliente.name) for cliente in self._clientes(empresa)
        ]

    @staticmethod
    def opcoes_de_pagamento(usuario, escopo):
        return [(codigo, _forma(codigo)) for codigo in PaymentMethod.values]

    def campos(self):
        return [
            Campo("cli", "Cliente", "escolha", opcoes=self.opcoes_de_cliente, obrigatorio=True),
            Campo("cnome", "Nome do cliente novo", "texto"),
            Campo("cdoc", "CNPJ/CPF do cliente", "texto"),
            Campo("cuf", "UF do cliente novo", "texto"),
            Campo("pag", "Pagamento", "escolha", opcoes=self.opcoes_de_pagamento, obrigatorio=True),
            Campo("uf", "UF de entrega", "texto", obrigatorio=True),
        ]

    def ajustar(self, dados, codigo, valor, usuario, escopo):
        empresa = self._empresa_ou_recusa(usuario, escopo, AjusteInvalido)
        novo = dict(dados.get("cliente_novo") or {})
        dados["cliente_novo"] = novo

        if codigo == "cli":
            if valor == CLIENTE_NOVO:
                dados["cliente_id"], dados["cliente_rotulo"] = None, ""
                return dados, self._aviso_cliente_novo(novo)
            cliente = self._clientes(empresa).filter(pk=valor).first()
            if cliente is None:
                raise AjusteInvalido("Este cliente não está mais disponível. Escolha outro.")
            dados["cliente_id"], dados["cliente_rotulo"] = cliente.pk, str(cliente)
            return dados, "Cliente: {}.".format(cliente.name)

        if codigo == "cdoc":
            digitos = only_digits(valor)
            if len(digitos) not in (11, 14):
                raise AjusteInvalido(DICA_DOCUMENTO)
            existente = self._clientes(empresa).filter(cnpj_cpf=digitos).first()
            if existente:
                dados["cliente_id"], dados["cliente_rotulo"] = existente.pk, str(existente)
                return dados, "Encontrei o cliente {} com este CNPJ/CPF: o pedido vai para ele.".format(existente.name)
            novo["cnpj_cpf"] = digitos
            if dados.get("cliente_id"):
                dados["cliente_id"], dados["cliente_rotulo"] = None, ""
                return dados, "Nenhum cliente tem este CNPJ/CPF: o pedido vai cadastrar um cliente novo."
            return dados, "CNPJ/CPF do cliente novo: {}.".format(format_cpf_cnpj(digitos))

        if codigo in ("cnome", "cuf"):
            if dados.get("cliente_id"):
                raise AjusteInvalido(MSG_CLIENTE_CADASTRADO.format(dados.get("cliente_rotulo", "")))
            if codigo == "cnome":
                novo["nome"] = _texto(valor, 100)
                return dados, "Nome do cliente novo: {}.".format(novo["nome"])
            novo["uf"] = _uf(valor) or self._recusar_uf()
            return dados, "UF do cliente novo: {}.".format(novo["uf"])

        if codigo == "pag":
            if valor not in PaymentMethod.values:
                raise AjusteInvalido("Escolha uma forma de pagamento da lista.")
            dados["payment_method"] = valor
            if valor not in METODOS_BOLETO:
                dados["installments"] = 1
                return dados, "Pagamento: {}.".format(_forma(valor))
            return dados, "Pagamento: {} em {}x. Para mudar as parcelas, use 🌐 Editar no site.".format(
                _forma(valor), dados.get("installments") or 1)

        if codigo == "uf":
            dados["uf"] = _uf(valor) or self._recusar_uf()
            return dados, "UF de entrega: {}.".format(dados["uf"])

        raise AjusteInvalido("Este campo não pode ser corrigido.")

    @staticmethod
    def _recusar_uf():
        raise AjusteInvalido(DICA_UF)

    # ── Resumo, form e confirmação ──

    def resumo(self, dados):
        novo = dados.get("cliente_novo") or {}
        if dados.get("cliente_id"):
            cliente = ("Cliente", dados.get("cliente_rotulo") or "—")
        else:
            local = "/".join(parte for parte in (novo.get("cidade"), novo.get("uf")) if parte)
            cliente = ("Cliente novo", " · ".join([
                novo.get("nome") or "falta o nome",
                format_cpf_cnpj(novo["cnpj_cpf"]) if novo.get("cnpj_cpf") else "falta o CNPJ/CPF",
                local if novo.get("uf") else (local + " · " if local else "") + "falta a UF",
            ]))

        forma = _forma(dados.get("payment_method"))
        if forma and dados.get("payment_method") in METODOS_BOLETO and (dados.get("installments") or 1) > 1:
            forma += " em {}x".format(dados["installments"])
        entrega = ", ".join(parte for parte in (dados.get("address"), dados.get("city")) if parte)
        entrega = "{}{}".format(entrega + " · " if entrega else "", dados.get("uf") or "falta a UF")

        linhas = [("Empresa", dados.get("empresa_nome") or "—"), cliente, ("Pagamento", forma or "falta escolher"),
                  ("Entrega", entrega)]
        documento = " · ".join(parte for parte in (
            "nº {}".format(dados["numero_documento"]) if dados.get("numero_documento") else "",
            date.fromisoformat(dados["data_documento"]).strftime("%d/%m/%Y") if dados.get("data_documento") else "",
        ) if parte)
        if documento:
            linhas.append(("Documento", documento))

        itens = dados.get("itens") or []
        total, descricoes = Decimal("0"), []
        for item in itens:
            preco, desconto = Decimal(item["preco"]), Decimal(item["desconto"])
            quantidade = item.get("quantidade")
            texto = "• {} × {} ({} cada)".format(quantidade or "?", item["rotulo"], _reais(preco))
            if desconto:
                texto += " − desconto {}".format(_reais(desconto))
            descricoes.append(texto)
            if quantidade:
                total += preco * quantidade - desconto
        linhas.append(("Itens ({})".format(len(itens)), "\n" + "\n".join(descricoes) if descricoes else "nenhum"))
        linhas.append(("Total", _reais(total)))
        linhas.append(("Ao confirmar", "o pedido vai para aprovação, o estoque é baixado e os gerentes são avisados."))
        return linhas

    def dados_para_form(self, dados):
        novo = dados.get("cliente_novo") or {}
        inicial = {
            "client": dados.get("cliente_id"),
            "payment_method": dados.get("payment_method") or "",
            "installments": dados.get("installments") or 1,
            "address": dados.get("address") or "",
            "city": dados.get("city") or "",
            "uf": dados.get("uf") or "",
            "cliente_nome": novo.get("nome") or "",
            "cliente_cnpj_cpf": novo.get("cnpj_cpf") or "",
            "cliente_endereco": novo.get("endereco") or "",
            "cliente_cidade": novo.get("cidade") or "",
            "cliente_uf": novo.get("uf") or "",
            "itens": dados.get("itens") or [],  # o form monta um campo de quantidade e um de desconto por item
        }
        for numero, item in enumerate(inicial["itens"]):
            inicial["item_{}_quantidade".format(numero)] = item.get("quantidade")
            inicial["item_{}_desconto".format(numero)] = item.get("desconto") or "0"
        return inicial

    def form(self, usuario, escopo, data=None, initial=None):
        return PedidoImportadoForm(
            data=data, initial=initial, empresa=self._empresa(usuario, escopo), itens=(initial or {}).get("itens", []),
        )

    def _recusa(self, form):
        """Os erros do form com as chaves que o bot entende (os códigos dos campos())."""
        erros = {}
        for nome, mensagens in form.errors.items():
            mensagens = [str(mensagem) for mensagem in mensagens]
            if nome in self.CAMPOS_DO_FORM:
                erros[self.CAMPOS_DO_FORM[nome]] = mensagens
            elif nome in form.fields:
                erros.setdefault("__all__", []).extend("{}: {}".format(form.fields[nome].label, m) for m in mensagens)
            else:
                erros.setdefault("__all__", []).extend(mensagens)
        return ImportacaoInvalida(erros, form=form)

    def confirmar(self, dados, usuario, escopo, dados_form=None):
        empresa = self._empresa(usuario, escopo)
        if empresa is None:
            raise ImportacaoInvalida({"__all__": [self.conferir_escopo(usuario, escopo)]})
        inicial = self.dados_para_form(dados)
        form = self.form(usuario, escopo, data=dados_form if dados_form is not None else inicial, initial=inicial)
        if not form.is_valid():
            raise self._recusa(form)

        with transaction.atomic():
            # As mesmas regras da tela de pedido: produtos travados, estoque conferido ao enviar
            itens, erros = services.conferir_itens(empresa, form.linhas(), enviando=True)
            if not erros and not itens:
                erros = ["Adicione pelo menos um produto ao pedido."]
            if erros:
                form.add_error(None, " | ".join(erros))
                raise self._recusa(form)

            pedido = form.save(commit=False)
            pedido.company, pedido.created_by, pedido.type = empresa, usuario, "OUT"
            pedido.client = form.cleaned_data["client"] or services.criar_cliente(form.cliente_form, empresa, usuario)
            try:
                services.salvar_pedido(pedido, itens, enviar=True)
            except pedidos.EstoqueInsuficiente as erro:
                form.add_error(None, str(erro))
                raise self._recusa(form) from None

        url = settings.SITE_URL + pedido.get_absolute_url()
        transaction.on_commit(lambda: services.notificar_gerentes_pedido_enviado(pedido, usuario, url))
        return pedido
