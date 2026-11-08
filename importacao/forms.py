from django import forms

from ia.models import ConfiguracaoIA

from .importadores import tipos_disponiveis
from .models import ConfiguracaoImportacao

MEGA = 1024 * 1024


class ArquivoForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo",
        help_text="Foto (JPG, PNG...) ou PDF do documento.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*,application/pdf"}),
    )

    def clean_arquivo(self):
        # Recusa pelo tamanho antes de ler o conteúdo
        arquivo = self.cleaned_data["arquivo"]
        limite_mb = ConfiguracaoIA.obter().tamanho_maximo_mb
        if arquivo.size > limite_mb * MEGA:
            raise forms.ValidationError(
                "O arquivo tem {:.1f} MB; o máximo é {} MB.".format(arquivo.size / MEGA, limite_mb).replace(".", ",", 1)
            )
        return arquivo


class NovaImportacaoForm(ArquivoForm):
    observacao = forms.CharField(
        label="Observação", required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Opcional. Algo que ajude a leitura, como de quem é o documento.",
    )
    tipo = forms.ChoiceField(label="Tipo de documento", help_text="O que é este documento.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipos = tipos_disponiveis()
        if len(tipos) > 1:
            self.fields["tipo"].choices = [("", "Escolha o tipo")] + tipos
        else:
            del self.fields["tipo"]  # com um tipo só, não há o que perguntar
        self.order_fields(["tipo", "arquivo", "observacao"])


class TipoForm(forms.Form):
    tipo = forms.ChoiceField(label="Tipo de documento")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [("", "Escolha o tipo")] + tipos_disponiveis()


class ConfiguracaoImportacaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoImportacao
        exclude = ["atualizado_em"]
