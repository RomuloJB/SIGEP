from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row
from django import forms

from .models import ConfiguracaoTelegram


class ConfiguracaoTelegramForm(forms.ModelForm):

    class Meta:
        model = ConfiguracaoTelegram
        exclude = ["atualizado_em"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agrupa os campos por assunto; o help_text de cada campo explica o número embaixo dele
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                "Quem está conectado",
                Row(
                    Column("mensagens_por_minuto", css_class="col-12 col-md-4"),
                    Column("arquivos_por_minuto", css_class="col-12 col-md-4"),
                    Column("bloqueio_minutos", css_class="col-12 col-md-4"),
                ),
            ),
            Fieldset(
                "Quem não está conectado",
                Row(
                    Column("desconhecido_mensagens_por_minuto", css_class="col-12 col-md-4"),
                    Column("desconhecido_bloqueio_minutos", css_class="col-12 col-md-4"),
                    Column("desconhecido_aviso_horas", css_class="col-12 col-md-4"),
                ),
            ),
            Fieldset(
                "Retenção do log",
                Row(
                    Column("reter_conteudo_dias", css_class="col-12 col-md-6"),
                    Column("reter_mensagens_dias", css_class="col-12 col-md-6"),
                ),
            ),
        )
