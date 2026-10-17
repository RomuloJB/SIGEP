from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django import forms
from django.utils.formats import number_format

from .models import ConfiguracaoIA, ConfiguracaoIAUsuario


class ConfiguracaoIAForm(forms.ModelForm):

    class Meta:
        model = ConfiguracaoIA
        exclude = ["atualizado_em"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agrupa os campos por assunto; o help_text de cada campo aparece embaixo dele
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Modelo",
                Row(
                    Column("provedor", css_class="col-12 col-md-4"),
                    Column("modelo", css_class="col-12 col-md-8"),
                ),
                Row(
                    Column("temperatura", css_class="col-12 col-md-4"),
                    Column("max_tokens_saida", css_class="col-12 col-md-4"),
                    Column("nivel_raciocinio", css_class="col-12 col-md-4"),
                ),
                Row(
                    Column("tentativas", css_class="col-12 col-md-4"),
                    Column("timeout_s", css_class="col-12 col-md-4"),
                ),
            ),
            Fieldset(
                "Limites padrão por usuário",
                Row(
                    Column("limite_mensal_usuario", css_class="col-12 col-md-4"),
                    Column("aviso_percentual", css_class="col-12 col-md-4"),
                    Column("reserva_minima_tokens", css_class="col-12 col-md-4"),
                ),
            ),
            Fieldset(
                "Proteção do sistema",
                Row(
                    Column("limite_mensal_sistema", css_class="col-12 col-md-6"),
                    Column("reter_requisicoes_dias", css_class="col-12 col-md-6"),
                ),
                Row(
                    Column("tamanho_maximo_mb", css_class="col-12 col-md-6"),
                    Column("pdf_max_paginas", css_class="col-12 col-md-6"),
                ),
            ),
            Fieldset(
                "Preços",
                Row(
                    Column("preco_entrada_milhao", css_class="col-12 col-md-6"),
                    Column("preco_saida_milhao", css_class="col-12 col-md-6"),
                ),
            ),
        )


class ConfiguracaoIAUsuarioForm(forms.ModelForm):

    class Meta:
        model = ConfiguracaoIAUsuario
        fields = ["ia_habilitada", "limite_mensal", "observacao"]

    def __init__(self, *args, limite_padrao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if limite_padrao is not None:
            self.fields["limite_mensal"].help_text = (
                "Tokens por mês para este usuário. Vazio = usa o padrão ({} tokens); 0 = nenhum token.".format(
                    number_format(limite_padrao, force_grouping=True)
                )
            )
