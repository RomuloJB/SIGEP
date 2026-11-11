from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row

from .masks import (
    CNPJ_DIGITS, CNPJ_FORMAT, CPF_DIGITS, CPF_FORMAT, LANDLINE_DIGITS, LANDLINE_FORMAT,
    PHONE_DIGITS, PHONE_FORMAT,
    format_cnpj, format_cpf, format_cpf_cnpj, format_phone, only_digits,
)
from .models import MAX_PARCELAS, METODOS_BOLETO, Client, Company, Order, PaymentMethod, Product


class MaskedDigitsField(forms.CharField):
    """
    Campo que grava só os dígitos. A máscara de digitação é aplicada pelo
    static/js/mascaras.js a partir do nome do campo (cpf, cnpj, phone...),
    então o nome do campo no form precisa conter um desses termos.
    """
    allowed_lengths = ()
    max_formatted_length = 0
    pattern = ""
    placeholder = ""
    invalid_message = ""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", self.max_formatted_length)
        super().__init__(**kwargs)
        self.error_messages["invalid"] = self.invalid_message

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.update({
            "inputmode": "numeric",
            "placeholder": self.placeholder,
            "pattern": self.pattern,
            # form-validation.js usa o title como mensagem de patternMismatch
            "title": self.invalid_message,
        })
        return attrs

    def format(self, value):
        raise NotImplementedError

    def to_python(self, value):
        value = super().to_python(value)
        return only_digits(value) if value else value

    def validate(self, value):
        super().validate(value)
        if value and len(value) not in self.allowed_lengths:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def prepare_value(self, value):
        return self.format(value)


class PhoneField(MaskedDigitsField):
    """Celular (NN) NNNNN-NNNN ou fixo (NN) NNNN-NNNN — User_Profile.phone (max_length=11)."""
    allowed_lengths = (LANDLINE_DIGITS, PHONE_DIGITS)
    max_formatted_length = len(PHONE_FORMAT)
    pattern = r"\(\d{2}\) \d{4,5}-\d{4}"
    placeholder = "(41) 99999-9999"
    invalid_message = f"Informe o telefone no formato {PHONE_FORMAT} ou {LANDLINE_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Celular ou fixo com DDD. Formato: {PHONE_FORMAT} ou {LANDLINE_FORMAT}")
        super().__init__(**kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.update({"inputmode": "tel", "autocomplete": "tel"})
        return attrs

    def format(self, value):
        return format_phone(value)


class CPFField(MaskedDigitsField):
    """CPF 000.000.000-00 — grava 11 dígitos (User_Profile.cpf tem max_length=14)."""
    allowed_lengths = (CPF_DIGITS,)
    max_formatted_length = len(CPF_FORMAT)
    pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    placeholder = CPF_FORMAT
    invalid_message = f"Informe o CPF no formato {CPF_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CPF_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cpf(value)


class CNPJField(MaskedDigitsField):
    """CNPJ 00.000.000/0000-00 — grava 14 dígitos (Company.cnpj tem max_length=18)."""
    allowed_lengths = (CNPJ_DIGITS,)
    max_formatted_length = len(CNPJ_FORMAT)
    pattern = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
    placeholder = CNPJ_FORMAT
    invalid_message = f"Informe o CNPJ no formato {CNPJ_FORMAT}."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CNPJ_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cnpj(value)


class CPFCNPJField(MaskedDigitsField):
    """CPF ou CNPJ, escolhido pela quantidade de dígitos (11 ou 14) — Client.cnpj_cpf."""
    allowed_lengths = (CPF_DIGITS, CNPJ_DIGITS)
    max_formatted_length = len(CNPJ_FORMAT)
    pattern = r"(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
    placeholder = f"{CPF_FORMAT} ou {CNPJ_FORMAT}"
    invalid_message = f"Informe um CPF ({CPF_FORMAT}) ou CNPJ ({CNPJ_FORMAT})."

    def __init__(self, **kwargs):
        kwargs.setdefault("help_text", f"Formato: {CNPJ_FORMAT} ou {CPF_FORMAT}")
        super().__init__(**kwargs)

    def format(self, value):
        return format_cpf_cnpj(value)


class ClientForm(forms.ModelForm):
    cnpj_cpf = CPFCNPJField(label="CNPJ/CPF")

    class Meta:
        model = Client
        fields = ["name", "cnpj_cpf", "address", "city", "uf"]
        widgets = {
            # Dropdown com busca (static/js/select-search.js): 7 estados visíveis e o resto
            # pela barra de rolagem; digitar filtra pelo nome ou pela sigla
            "uf": forms.Select(attrs={
                "data-tom-select": "",
                "data-placeholder": "Busque o estado…",
                "data-opcoes-visiveis": "7",
                "data-buscar-pelo-valor": "",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agrupa campos curtos na mesma linha (grid do Bootstrap; empilha no celular)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-12 col-md-8"),
                Column("cnpj_cpf", css_class="col-12 col-md-4"),
            ),
            Row(
                Column("address", css_class="col-12 col-md-5"),
                Column("city", css_class="col-12 col-md-4"),
                # Mais largo que a sigla: o dropdown mostra o nome do estado
                Column("uf", css_class="col-12 col-md-3"),
            ),
        )


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "description", "sku", "color", "unit_value", "stock", "measure_unit"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agrupa campos curtos na mesma linha (grid do Bootstrap; empilha no celular)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-12 col-md-8"),
                Column("sku", css_class="col-12 col-md-4"),
            ),
            "description",
            Row(
                Column("color", css_class="col-12 col-md-3"),
                Column("measure_unit", css_class="col-12 col-md-3"),
                Column("unit_value", css_class="col-12 col-md-3"),
                Column("stock", css_class="col-12 col-md-3"),
            ),
        )


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["type", "client", "payment_method", "installments", "address", "city", "uf"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["installments"].widget.attrs.update({"min": 1, "max": MAX_PARCELAS})
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True  # o order_form.html já tem o csrf_token
        self.helper.layout = Layout(
            Row(
                Column("type", css_class="col-12 col-md-3"),
                Column("client", css_class="col-12 col-md"),
                Column("payment_method", css_class="col-12 col-md-3"),
                # O order-scripts.js mostra este campo só nos métodos de boleto
                Column(
                    "installments", css_class="col-12 col-md-2", css_id="campo-parcelas",
                    data_metodos_boleto=",".join(METODOS_BOLETO),
                ),
            ),
            Row(
                Column("address", css_class="col-12 col-md-7"),
                Column("city", css_class="col-12 col-md-3"),
                Column("uf", css_class="col-12 col-md-2"),
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        # Fora do boleto vale sempre 1 parcela, mesmo que tenha chegado outro valor
        if cleaned_data.get("payment_method") not in METODOS_BOLETO:
            self.errors.pop("installments", None)
            cleaned_data["installments"] = 1
        return cleaned_data


class PedidoImportadoForm(OrderForm):
    """
    Revisão de um pedido lido de um documento (cadastros/importacao.py): o cabeçalho do pedido,
    o cliente novo (quando o cliente do documento ainda não está cadastrado) e a quantidade e o
    desconto de cada item lido. O pedido importado é sempre de venda: o tipo não aparece.
    `itens` é a lista do rascunho ({"produto_id", "rotulo", ...}); os produtos não mudam aqui.
    """
    # Campo do ClientForm -> campo deste form
    CAMPOS_DO_CLIENTE = {
        "name": "cliente_nome", "cnpj_cpf": "cliente_cnpj_cpf", "address": "cliente_endereco",
        "city": "cliente_cidade", "uf": "cliente_uf",
    }

    cliente_nome = forms.CharField(label="Nome do cliente novo", max_length=100, required=False)
    cliente_cnpj_cpf = CPFCNPJField(label="CNPJ/CPF do cliente novo", required=False)
    cliente_endereco = forms.CharField(label="Endereço do cliente novo", max_length=100, required=False)
    cliente_cidade = forms.CharField(label="Cidade do cliente novo", max_length=100, required=False)
    cliente_uf = forms.CharField(label="UF do cliente novo", max_length=2, required=False, help_text="Exemplo: PR")

    class Meta(OrderForm.Meta):
        fields = ["client", "payment_method", "installments", "address", "city", "uf"]

    def __init__(self, *args, empresa=None, itens=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        self.itens = list(itens)
        self.cliente_form = None
        # O layout do OrderForm tem o tipo, que aqui não existe: os campos vão um embaixo do outro
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True

        cliente = self.fields["client"]
        cliente.queryset = Client.objects.filter(company=empresa) if empresa else Client.objects.none()
        cliente.required = False
        cliente.empty_label = "➕ Cliente novo (dados abaixo)"
        cliente.help_text = "Escolha um cliente cadastrado ou deixe em “Cliente novo” para cadastrá-lo com os dados abaixo."
        # O model tem Pix como padrão, então o select viria sem a opção vazia: aqui a forma
        # que não foi lida fica em branco, para a pessoa escolher
        self.fields["payment_method"].choices = [("", "---------")] + list(PaymentMethod.choices)

        ids = [item["produto_id"] for item in self.itens]
        estoque = dict(Product.objects.filter(company=empresa, pk__in=ids).values_list("pk", "stock")) if empresa else {}
        for numero, item in enumerate(self.itens):
            rotulo = item.get("rotulo", "")
            self.fields["item_{}_quantidade".format(numero)] = forms.IntegerField(
                label="Quantidade · {}".format(rotulo), min_value=0,
                help_text="Estoque agora: {}. Zero tira o item do pedido.".format(estoque.get(item["produto_id"], 0)),
            )
            self.fields["item_{}_desconto".format(numero)] = forms.DecimalField(
                label="Desconto (R$) · {}".format(rotulo), min_value=0, max_digits=10, decimal_places=2, required=False,
                help_text="Desconto sobre o total do item. Exemplo: 5.00",
            )

    def clean_cliente_uf(self):
        return (self.cleaned_data.get("cliente_uf") or "").strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("client"):
            self._conferir_cliente_novo(cleaned_data)
        return cleaned_data

    def _conferir_cliente_novo(self, cleaned_data):
        """Sem cliente escolhido, o cliente novo passa pelo ClientForm, o mesmo da tela de cadastro."""
        dados = {campo: cleaned_data.get(nosso) or "" for campo, nosso in self.CAMPOS_DO_CLIENTE.items()}
        self.cliente_form = ClientForm(data=dados)
        if not self.cliente_form.is_valid():
            for campo, mensagens in self.cliente_form.errors.items():
                nosso = self.CAMPOS_DO_CLIENTE.get(campo)
                if nosso and nosso not in self.errors:
                    for mensagem in mensagens:
                        self.add_error(nosso, mensagem)
            return
        repetido = Client.objects.filter(company=self.empresa, cnpj_cpf=self.cliente_form.cleaned_data["cnpj_cpf"]).first()
        if repetido:
            self.add_error("cliente_cnpj_cpf", 'O cliente "{}" já tem este CNPJ/CPF: escolha-o em Cliente.'.format(repetido.name))

    def linhas(self):
        """Os itens no formato do cadastros.services.conferir_itens. Quantidade zero tira o item."""
        linhas = []
        for numero, item in enumerate(self.itens):
            quantidade = self.cleaned_data.get("item_{}_quantidade".format(numero))
            if not quantidade:
                continue
            desconto = self.cleaned_data.get("item_{}_desconto".format(numero)) or 0
            linhas.append((str(item["produto_id"]), str(quantidade), str(desconto)))
        return linhas


class UserSearchMultipleField(forms.ModelMultipleChoiceField):
    """
    Seleção múltipla de usuários como dropdown com busca e "chips" removíveis
    (Tom Select, inicializado pelo static/js/select-search.js via data-tom-select).
    Escala melhor que um checkbox por usuário quando a base cresce.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", User.objects.order_by("first_name", "last_name", "username"))
        kwargs.setdefault("widget", forms.SelectMultiple(attrs={
            "data-tom-select": "",
            "data-placeholder": "Busque por nome ou usuário…",
        }))
        super().__init__(**kwargs)

    def label_from_instance(self, user):
        # Nome completo + usuário, para a busca encontrar por qualquer um dos dois
        full_name = user.get_full_name()
        return f"{full_name} ({user.username})" if full_name else user.username


class CompanyForm(forms.ModelForm):
    cnpj = CNPJField(label="CNPJ")
    manager = UserSearchMultipleField(label="Gerentes")
    sales_rep = UserSearchMultipleField(required=False, label="Representantes")

    class Meta:
        model = Company
        fields = ["name", "session_name", "description", "cnpj", "manager", "sales_rep"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-12 col-md-8"),
                Column("cnpj", css_class="col-12 col-md-4"),
            ),
            Row(
                Column("session_name", css_class="col-12 col-md-6"),
            ),
            "description",
            "manager",
            "sales_rep",
        )
