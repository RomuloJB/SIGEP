from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConfiguracaoIA(models.Model):
    """
    Configuração única (pk=1) do uso de IA: modelo, limites, cotas e preços.
    A chave de API NÃO fica aqui: vem só do .env (GEMINI_API_KEY).
    """
    CHAVE_CACHE = "ia:configuracao"
    SEGUNDOS_CACHE = 30

    class Provedor(models.TextChoices):
        GEMINI = "gemini", "Google Gemini"
        FALSO = "falso", "Falso (testes, sem rede)"

    class NivelRaciocinio(models.TextChoices):
        PADRAO = "", "Padrão do modelo"
        LOW = "low", "Baixo"
        MEDIUM = "medium", "Médio"
        HIGH = "high", "Alto"

    # Modelo
    provedor = models.CharField(
        max_length=20, choices=Provedor.choices, default=Provedor.GEMINI, verbose_name="provedor",
        help_text="Serviço de IA usado nas chamadas. \"Falso\" responde sem rede e serve só para testes.",
    )
    modelo = models.CharField(
        max_length=100, default="gemini-3.5-flash-lite", verbose_name="modelo",
        help_text="Nome do modelo no provedor, exatamente como na documentação dele.",
    )
    temperatura = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("2"))],
        verbose_name="temperatura",
        help_text="De 0 a 2. Quanto menor, mais previsíveis as respostas.",
    )
    max_tokens_saida = models.PositiveIntegerField(
        default=8192, validators=[MinValueValidator(1)], verbose_name="máximo de tokens de saída",
        help_text="Limite de tokens que o modelo pode gerar em uma resposta, incluindo o raciocínio.",
    )
    nivel_raciocinio = models.CharField(
        max_length=10, choices=NivelRaciocinio.choices, default=NivelRaciocinio.LOW, blank=True,
        verbose_name="nível de raciocínio",
        help_text="Quanto o modelo \"pensa\" antes de responder. Os níveis valem do Gemini 3 em diante; "
                  "com um modelo 2.5, deixe este campo vazio (padrão do modelo).",
    )
    tentativas = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1)], verbose_name="tentativas",
        help_text="Quantas vezes tentar a mesma chamada quando o erro for temporário (inclui a primeira).",
    )
    timeout_s = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(1)], verbose_name="tempo limite (s)",
        help_text="Segundos de espera pela resposta do provedor antes de desistir.",
    )

    # Cotas
    limite_mensal_usuario = models.PositiveIntegerField(
        default=100000, verbose_name="limite mensal por usuário",
        help_text="Tokens que cada usuário pode gastar por mês, quando não tiver um limite próprio.",
    )
    aviso_percentual = models.PositiveSmallIntegerField(
        default=80, validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="aviso (%)",
        help_text="Percentual da cota mensal a partir do qual o usuário é avisado.",
    )
    reserva_minima_tokens = models.PositiveIntegerField(
        default=5000, verbose_name="reserva mínima de tokens",
        help_text="Saldo mínimo de tokens que o usuário precisa ter para iniciar uma nova chamada.",
    )
    limite_mensal_sistema = models.PositiveBigIntegerField(
        default=20000000, verbose_name="limite mensal do sistema",
        help_text="Tokens que o sistema inteiro pode gastar por mês, somando todos os usuários. 0 desliga este limite.",
    )

    # Arquivos e retenção
    tamanho_maximo_mb = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1)], verbose_name="tamanho máximo (MB)",
        help_text="Tamanho máximo de cada arquivo enviado à IA, em megabytes.",
    )
    pdf_max_paginas = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1)], verbose_name="máximo de páginas do PDF",
        help_text="Número máximo de páginas de um PDF enviado à IA.",
    )
    reter_requisicoes_dias = models.PositiveSmallIntegerField(
        default=60, verbose_name="reter requisições (dias)",
        help_text="Por quantos dias os registros das chamadas são guardados antes de serem apagados "
                  "pela limpeza diária. O consumo do mês não é apagado. 0 = nunca apagar.",
    )

    # Preços (só para estimar custo)
    preco_entrada_milhao = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="preço de entrada (US$/milhão)",
        help_text="Preço em dólares por milhão de tokens de entrada. Opcional; usado só para estimar custo.",
    )
    preco_saida_milhao = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="preço de saída (US$/milhão)",
        help_text="Preço em dólares por milhão de tokens de saída (inclui raciocínio). Opcional; usado só para estimar custo.",
    )

    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="atualizado em",
        help_text="Data da última alteração. Ao mudar, o cliente do provedor é recriado.",
    )

    def __str__(self):
        return "Configuração de IA ({} / {})".format(self.get_provedor_display(), self.modelo)

    def save(self, *args, **kwargs):
        self.pk = 1  # linha única
        super().save(*args, **kwargs)
        cache.delete(self.CHAVE_CACHE)

    @classmethod
    def obter(cls):
        """Devolve a configuração única, criando-a com os padrões se ainda não existir."""
        config = cache.get(cls.CHAVE_CACHE)
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CHAVE_CACHE, config, cls.SEGUNDOS_CACHE)
        return config

    class Meta:
        verbose_name = "Configuração de IA"
        verbose_name_plural = "Configuração de IA"


class ConfiguracaoIAUsuario(models.Model):
    """Exceções por usuário. Sem linha para o usuário, valem os padrões da ConfiguracaoIA."""
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="configuracao_ia",
        verbose_name="usuário", help_text="Usuário a quem esta configuração se aplica.",
    )
    ia_habilitada = models.BooleanField(
        default=True, verbose_name="IA habilitada",
        help_text="Desmarque para impedir que este usuário use qualquer recurso de IA.",
    )
    limite_mensal = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="limite mensal",
        help_text="Tokens por mês para este usuário. Vazio = usa o limite padrão da configuração; 0 = nenhum token.",
    )
    observacao = models.CharField(
        max_length=255, blank=True, verbose_name="observação",
        help_text="Motivo da exceção (ex.: \"gerente com uso maior\").",
    )

    def __str__(self):
        return "Configuração de IA de {}".format(self.usuario)

    class Meta:
        verbose_name = "Configuração de IA do usuário"
        verbose_name_plural = "Configurações de IA dos usuários"


class RequisicaoIA(models.Model):
    """
    Auditoria: uma linha POR TENTATIVA de chamada à IA (inclusive as bloqueadas antes
    de chegar ao provedor, com tentativa 0). Não guarda arquivos nem o texto enviado.
    """
    TAMANHO_MAXIMO_RESPOSTA = 20000

    class Origem(models.TextChoices):
        SITE = "site", "Site"
        TELEGRAM = "telegram", "Telegram"
        COMANDO = "comando", "Comando (manage.py)"

    class Situacao(models.TextChoices):
        SUCESSO = "sucesso", "Sucesso"
        RESPOSTA_INVALIDA = "resposta_invalida", "Resposta inválida"
        ERRO_TEMPORARIO = "erro_temporario", "Erro temporário"
        ERRO_PERMANENTE = "erro_permanente", "Erro permanente"
        TEMPO_ESGOTADO = "tempo_esgotado", "Tempo esgotado"
        BLOQUEADA_COTA = "bloqueada_cota", "Bloqueada pela cota"
        BLOQUEADA_SEGURANCA = "bloqueada_seguranca", "Bloqueada por segurança"
        INDISPONIVEL = "indisponivel", "Indisponível"
        ERRO_CONFIGURACAO = "erro_configuracao", "Erro de configuração"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requisicoes_ia",
        verbose_name="usuário", help_text="Quem fez a chamada.",
    )
    referencia_tipo = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="tipo da referência",
        help_text="Tipo do registro ao qual a chamada se refere (ex.: pedido, conversa).",
    )
    referencia_id = models.PositiveBigIntegerField(
        null=True, blank=True, verbose_name="id da referência",
        help_text="Id do registro ao qual a chamada se refere.",
    )
    referencia = GenericForeignKey("referencia_tipo", "referencia_id")
    origem = models.CharField(
        max_length=20, choices=Origem.choices, default=Origem.SITE, verbose_name="origem",
        help_text="Por onde a chamada entrou no sistema.",
    )
    finalidade = models.CharField(
        max_length=60, db_index=True, verbose_name="finalidade",
        help_text="Para que serve a chamada, no padrão app_acao (ex.: chatbot_responder).",
    )
    provedor = models.CharField(max_length=20, verbose_name="provedor", help_text="Provedor de IA usado.")
    modelo = models.CharField(max_length=100, blank=True, verbose_name="modelo", help_text="Modelo que respondeu (ou o configurado, se não houve resposta).")
    versao_prompt = models.CharField(
        max_length=50, blank=True, verbose_name="versão do prompt",
        help_text="Versão das instruções usadas, para comparar resultados entre versões.",
    )
    tentativa = models.PositiveSmallIntegerField(
        default=1, verbose_name="tentativa",
        help_text="Número da tentativa (1, 2...). 0 = bloqueada antes de chamar o provedor.",
    )
    situacao = models.CharField(
        max_length=30, choices=Situacao.choices, verbose_name="situação", help_text="Resultado da tentativa.",
    )
    tokens_entrada = models.PositiveIntegerField(default=0, verbose_name="tokens de entrada", help_text="Tokens do que foi enviado.")
    tokens_saida = models.PositiveIntegerField(default=0, verbose_name="tokens de saída", help_text="Tokens gerados, incluindo o raciocínio.")
    tokens_raciocinio = models.PositiveIntegerField(default=0, verbose_name="tokens de raciocínio", help_text="Parte dos tokens de saída gasta em raciocínio (informativo).")
    tokens_total = models.PositiveIntegerField(default=0, verbose_name="tokens no total", help_text="Entrada + saída.")
    custo_estimado = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("0"), verbose_name="custo estimado (US$)",
        help_text="Tokens x preços da configuração. 0 quando não há preço cadastrado.",
    )
    duracao_ms = models.PositiveIntegerField(default=0, verbose_name="duração (ms)", help_text="Tempo da tentativa em milissegundos.")
    motivo_fim = models.CharField(max_length=50, blank=True, verbose_name="motivo do fim", help_text="Por que o modelo parou de gerar (ex.: STOP, MAX_TOKENS, SAFETY).")
    arquivo_mime = models.CharField(max_length=100, blank=True, verbose_name="tipo do arquivo", help_text="Tipo MIME do arquivo enviado, se houver.")
    arquivo_tamanho = models.PositiveIntegerField(null=True, blank=True, verbose_name="tamanho do arquivo (bytes)", help_text="Tamanho do arquivo enviado, se houver.")
    arquivo_hash = models.CharField(max_length=64, blank=True, verbose_name="hash do arquivo", help_text="SHA-256 do arquivo enviado. O arquivo em si não é guardado.")
    resposta = models.TextField(blank=True, verbose_name="resposta", help_text="Texto devolvido pela IA, cortado em 20 mil caracteres.")
    erro = models.TextField(blank=True, verbose_name="erro", help_text="Mensagem de erro, quando a tentativa falhou.")
    contexto_hash = models.CharField(
        max_length=64, blank=True, verbose_name="hash do contexto",
        help_text="SHA-256 do texto enviado (instruções, histórico e mensagem). O texto em si não é guardado.",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Momento da tentativa.")

    def __str__(self):
        return "{} | {} | {} | {}".format(self.criado_em, self.usuario, self.finalidade, self.get_situacao_display())

    class Meta:
        verbose_name = "Requisição de IA"
        verbose_name_plural = "Requisições de IA"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["usuario", "-criado_em"], name="ia_req_usuario_criado"),
            models.Index(fields=["situacao", "-criado_em"], name="ia_req_situacao_criado"),
            models.Index(fields=["referencia_tipo", "referencia_id", "-criado_em"], name="ia_req_referencia_criado"),
        ]


class ConsumoIA(models.Model):
    """
    Consumo de tokens por usuário e mês (dono da cota = usuário). A cota "zera" sozinha
    porque cada mês tem a sua linha: não há contador para reiniciar.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="consumos_ia",
        verbose_name="usuário", help_text="Dono da cota.",
    )
    mes = models.DateField(verbose_name="mês", help_text="Sempre o dia 1 do mês (fuso America/Sao_Paulo).")
    tokens_entrada = models.PositiveBigIntegerField(default=0, verbose_name="tokens de entrada", help_text="Soma dos tokens de entrada no mês.")
    tokens_saida = models.PositiveBigIntegerField(default=0, verbose_name="tokens de saída", help_text="Soma dos tokens de saída no mês, incluindo o raciocínio.")
    tokens_total = models.PositiveBigIntegerField(default=0, verbose_name="tokens no total", help_text="Entrada + saída: é o valor comparado com a cota.")
    custo_estimado = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("0"), verbose_name="custo estimado (US$)",
        help_text="Soma do custo estimado das requisições do mês.",
    )
    requisicoes = models.PositiveIntegerField(default=0, verbose_name="requisições", help_text="Tentativas do mês que consumiram tokens.")

    def __str__(self):
        return "{} | {:%m/%Y} | {} tokens".format(self.usuario, self.mes, self.tokens_total)

    class Meta:
        verbose_name = "Consumo de IA"
        verbose_name_plural = "Consumo de IA"
        ordering = ["-mes", "usuario"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "mes"], name="ia_consumo_usuario_mes_unico"),
        ]
