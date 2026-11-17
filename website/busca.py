"""
Busca geral das listagens: o campo "Buscar" do card procura em todos os registros
(?q=), e não só nas linhas da página atual. Vale junto com os filtros e a paginação.

Cada listagem diz onde procurar:

    class ClientList(BuscaGeralMixin, ..., PaginatedFilterView):
        busca_campos = ("name", "uf")         # texto: contém, sem diferenciar maiúsculas e acentos
        busca_escolhas = ("status",)          # campos com choices: procura no rótulo exibido
        busca_digitos = ("cnpj_cpf",)         # CPF/CNPJ/telefone gravados só com dígitos
        busca_numeros = ("pk",)               # inteiros exatos: "12" ou "#12"

Várias palavras: cada uma precisa aparecer em algum dos campos ("maria pr" acha a
Maria do PR). Os campos podem ser de relações ("client__name") e anotações da view
("usuario_site"): a busca é aplicada depois do get_queryset da view.

O app importacao não pode importar este módulo (não importa apps do projeto): a lista
de importações tem a sua versão enxuta em importacao/busca.py.
"""
import re
import unicodedata

from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Cast, Lower

PARAMETRO = "q"
TAMANHO_MAXIMO = 100

COM_ACENTO = "áàâãäéèêëíìîïóòôõöúùûüçñ"
SEM_ACENTO = "aaaaaeeeeiiiiooooouuuucn"
MAIOR_INTEIRO = 2 ** 63 - 1  # bigint do Postgres


def sem_acento(texto):
    """Minúsculas e sem acentos, como a coluna fica para comparar."""
    decomposto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def coluna_sem_acento(campo):
    """A coluna em minúsculas e sem acentos (TRANSLATE do Postgres, sem extensão)."""
    texto = Lower(Cast(F(campo), output_field=CharField()))
    return Func(texto, Value(COM_ACENTO), Value(SEM_ACENTO), function="TRANSLATE", output_field=CharField())


def campo_do_model(model, caminho):
    """O campo do model no fim de "client__name"; None para anotações e caminhos desconhecidos."""
    campo = None
    for parte in caminho.split("__"):
        try:
            campo = model._meta.get_field(parte)
        except FieldDoesNotExist:
            return None
        model = campo.related_model or model
    return campo


def valores_pelo_rotulo(model, caminho, palavra):
    """Valores gravados cujo rótulo (ou o próprio valor) contém a palavra."""
    campo = campo_do_model(model, caminho)
    if campo is None or not campo.choices:
        return []
    return [
        valor for valor, rotulo in campo.flatchoices
        if palavra in sem_acento(rotulo) or palavra in sem_acento(valor)
    ]


def aplicar(queryset, termo, campos=(), escolhas=(), digitos=(), numeros=()):
    """O queryset só com os registros em que cada palavra do termo aparece em algum campo."""
    palavras = [sem_acento(p) for p in termo.split()]
    if not palavras:
        return queryset

    apelidos = {"_busca_{}".format(i): coluna_sem_acento(campo) for i, campo in enumerate(campos)}
    if apelidos:
        queryset = queryset.alias(**apelidos)

    for palavra in palavras:
        condicao = Q()
        for apelido in apelidos:
            condicao |= Q(**{apelido + "__contains": palavra})
        for campo in escolhas:
            valores = valores_pelo_rotulo(queryset.model, campo, palavra)
            if valores:
                condicao |= Q(**{campo + "__in": valores})
        so_digitos = re.sub(r"\D", "", palavra)
        if so_digitos:
            for campo in digitos:
                condicao |= Q(**{campo + "__contains": so_digitos})
        numero = palavra.lstrip("#")
        if numero.isdigit() and int(numero) <= MAIOR_INTEIRO:
            for campo in numeros:
                condicao |= Q(**{campo: int(numero)})
        # Nenhum campo aceita a palavra: nada bate (Q() vazio deixaria tudo passar)
        queryset = queryset.filter(condicao) if condicao else queryset.none()
    return queryset


class BuscaGeralMixin:
    """
    Busca do campo "Buscar" do card em todos os registros (ver o topo do módulo).
    Em FilterView, entra depois do get_queryset da view (anotações valem); numa
    ListView sem filtro, chame self.aplicar_busca(queryset) no get_queryset.
    """
    busca_campos = ()
    busca_escolhas = ()
    busca_digitos = ()
    busca_numeros = ()

    def termo_da_busca(self):
        return self.request.GET.get(PARAMETRO, "").strip()[:TAMANHO_MAXIMO]

    def aplicar_busca(self, queryset):
        return aplicar(
            queryset, self.termo_da_busca(),
            self.busca_campos, self.busca_escolhas, self.busca_digitos, self.busca_numeros,
        )

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs["queryset"] = self.aplicar_busca(kwargs["queryset"])
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["busca"] = self.termo_da_busca()
        return context
