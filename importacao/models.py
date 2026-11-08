from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .importadores import obter_importador


class TransicaoInvalida(ValueError):
    """Mudança de situação que o diagrama da importação não permite."""


class Importacao(models.Model):
    """
    Rascunho genérico: um arquivo lido pela IA, que a pessoa confere antes de virar registro.
    O arquivo em si não é guardado: só o tipo, o tamanho e o hash.
    """

    class Origem(models.TextChoices):
        SITE = "site", "Site"
        TELEGRAM = "telegram", "Telegram"

    class Situacao(models.TextChoices):
        AGUARDANDO_TIPO = "aguardando_tipo", "Aguardando tipo"
        PROCESSANDO = "processando", "Lendo"
        PRONTA = "pronta", "Para revisar"
        CONFIRMADA = "confirmada", "Confirmada"
        DESCARTADA = "descartada", "Descartada"
        FALHOU = "falhou", "Falhou"
        NAO_RECONHECIDA = "nao_reconhecida", "Não reconhecida"
        BLOQUEADA = "bloqueada", "Sem cota"
        EXPIRADA = "expirada", "Expirada"

    # Só estas mudanças de situação existem; mudar_situacao() recusa o resto
    TRANSICOES = {
        Situacao.AGUARDANDO_TIPO: {Situacao.PROCESSANDO, Situacao.DESCARTADA, Situacao.EXPIRADA},
        Situacao.PROCESSANDO: {Situacao.PRONTA, Situacao.FALHOU, Situacao.NAO_RECONHECIDA, Situacao.BLOQUEADA},
        Situacao.PRONTA: {Situacao.CONFIRMADA, Situacao.DESCARTADA, Situacao.EXPIRADA},
        Situacao.FALHOU: {Situacao.PROCESSANDO, Situacao.DESCARTADA},
        Situacao.NAO_RECONHECIDA: {Situacao.PROCESSANDO, Situacao.DESCARTADA},
        Situacao.BLOQUEADA: {Situacao.PROCESSANDO, Situacao.DESCARTADA},
        Situacao.CONFIRMADA: set(),
        Situacao.DESCARTADA: set(),
        Situacao.EXPIRADA: set(),
    }
    ABERTAS = (Situacao.AGUARDANDO_TIPO, Situacao.PROCESSANDO, Situacao.PRONTA)
    PODEM_TENTAR_DE_NOVO = (Situacao.FALHOU, Situacao.NAO_RECONHECIDA, Situacao.BLOQUEADA)
    ENCERRADAS = (
        Situacao.CONFIRMADA, Situacao.DESCARTADA, Situacao.EXPIRADA,
        Situacao.FALHOU, Situacao.NAO_RECONHECIDA, Situacao.BLOQUEADA,
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="importacoes",
        verbose_name="criado por", help_text="Quem enviou o arquivo. Só essa pessoa vê e confirma a importação.",
    )
    tipo = models.CharField(
        max_length=60, blank=True, verbose_name="tipo",
        help_text="Importador usado, no formato app.entidade. Vazio enquanto aguarda a escolha do tipo.",
    )
    origem = models.CharField(
        max_length=20, choices=Origem.choices, default=Origem.SITE, verbose_name="origem",
        help_text="Por onde o arquivo chegou.",
    )
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.AGUARDANDO_TIPO, verbose_name="situação",
        help_text="Etapa da importação.",
    )
    observacao = models.TextField(
        blank=True, verbose_name="observação",
        help_text="Texto enviado junto com o arquivo (legenda no Telegram). Vai para a IA como dado.",
    )
    arquivo_nome = models.CharField(max_length=255, blank=True, verbose_name="nome do arquivo", help_text="Nome original do arquivo.")
    arquivo_mime = models.CharField(max_length=100, blank=True, verbose_name="tipo do arquivo", help_text="Tipo MIME, ex.: application/pdf.")
    arquivo_tamanho = models.PositiveIntegerField(null=True, blank=True, verbose_name="tamanho (bytes)", help_text="Tamanho do arquivo enviado.")
    arquivo_hash = models.CharField(
        max_length=64, blank=True, verbose_name="hash do arquivo",
        help_text="SHA-256 do arquivo. Serve para reaproveitar uma leitura e avisar de documento repetido.",
    )
    extracao = models.JSONField(
        null=True, blank=True, verbose_name="extração",
        help_text="Resposta da IA como veio, já validada pelo esquema. Serve para investigar e reaproveitar.",
    )
    dados = models.JSONField(default=dict, blank=True, verbose_name="dados", help_text="O rascunho conferido, que a pessoa edita.")
    avisos = models.JSONField(default=list, blank=True, verbose_name="avisos", help_text="Pontos para a pessoa conferir com atenção.")
    mensagem_erro = models.TextField(
        blank=True, verbose_name="mensagem de erro",
        help_text="Motivo da falha, pronto para mostrar à pessoa. O texto técnico fica só no log e na auditoria da IA.",
    )
    versao_prompt = models.CharField(max_length=50, blank=True, verbose_name="versão do prompt", help_text="Versão das instruções usadas na leitura.")
    tentativas = models.PositiveSmallIntegerField(default=0, verbose_name="tentativas", help_text="Quantas leituras foram iniciadas.")
    processando_desde = models.DateTimeField(
        null=True, blank=True, verbose_name="lendo desde",
        help_text="Início da leitura em andamento. Trava a importação para não ser lida duas vezes ao mesmo tempo.",
    )
    processada_em = models.DateTimeField(null=True, blank=True, verbose_name="lida em", help_text="Fim da última leitura.")
    confirmada_em = models.DateTimeField(null=True, blank=True, verbose_name="confirmada em", help_text="Quando o registro foi criado.")
    descartada_em = models.DateTimeField(null=True, blank=True, verbose_name="descartada em", help_text="Quando a pessoa descartou.")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Quando o arquivo chegou.")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="atualizado em", help_text="Última alteração.")

    objeto_tipo = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="tipo do registro criado",
        help_text="Tipo do registro criado na confirmação.",
    )
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="id do registro criado", help_text="Id do registro criado.")
    objeto = GenericForeignKey("objeto_tipo", "objeto_id")

    def __str__(self):
        return "Importação #{} ({})".format(self.pk, self.nome_do_tipo)

    @property
    def importador(self):
        return obter_importador(self.tipo)

    @property
    def nome_do_tipo(self):
        importador = self.importador
        return importador.nome if importador else (self.tipo or "tipo a escolher")

    def pode_mudar_para(self, nova):
        return nova in self.TRANSICOES[self.situacao]

    @property
    def pode_descartar(self):
        return self.pode_mudar_para(self.Situacao.DESCARTADA)

    @property
    def pode_tentar_de_novo(self):
        return self.situacao in self.PODEM_TENTAR_DE_NOVO

    def mudar_situacao(self, nova):
        """Muda a situação (sem salvar) e acerta as datas. Devolve a anterior; levanta TransicaoInvalida."""
        if not self.pode_mudar_para(nova):
            raise TransicaoInvalida("Uma importação {} não pode passar a {}.".format(
                self.get_situacao_display().lower(), self.Situacao(nova).label.lower(),
            ))
        anterior, agora = self.situacao, timezone.now()
        if anterior == self.Situacao.PROCESSANDO:
            self.processada_em = agora
        if nova == self.Situacao.CONFIRMADA:
            self.confirmada_em = agora
        elif nova == self.Situacao.DESCARTADA:
            self.descartada_em = agora
        # Entrando ou saindo de "lendo", a trava recomeça: quem pega a leitura marca o início
        self.processando_desde = None
        self.situacao = nova
        return anterior

    class Meta:
        verbose_name = "Importação"
        verbose_name_plural = "Importações"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["criado_por", "situacao"], name="imp_criado_por_situacao"),
            models.Index(fields=["criado_por", "arquivo_hash"], name="imp_criado_por_hash"),
        ]


class ArquivoTemporario(models.Model):
    """
    O arquivo enviado pelo site, guardado só até a leitura começar: a tarefa lê e apaga. Existe
    porque o Cloud Tasks não aceita tarefas grandes (1 MB) e um PDF pode ter até o limite da IA.
    """
    importacao = models.OneToOneField(
        Importacao, on_delete=models.CASCADE, related_name="arquivo_temporario", verbose_name="importação",
        help_text="Importação que vai ler este arquivo.",
    )
    conteudo = models.BinaryField(verbose_name="conteúdo", help_text="Bytes do arquivo, apagados quando a leitura começa.")
    mime = models.CharField(max_length=100, blank=True, verbose_name="tipo do arquivo", help_text="Tipo MIME informado no envio.")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Quando o arquivo foi guardado.")

    def __str__(self):
        return "Arquivo da importação #{}".format(self.importacao_id)

    class Meta:
        verbose_name = "Arquivo temporário"
        verbose_name_plural = "Arquivos temporários"


class ConfiguracaoImportacao(models.Model):
    """Configuração única (pk=1) dos limites e prazos da importação."""
    CHAVE_CACHE = "importacao:configuracao"
    SEGUNDOS_CACHE = 30

    importacoes_por_hora = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1)], verbose_name="importações por hora",
        help_text="Quantos arquivos cada pessoa pode enviar por hora.",
    )
    leituras_simultaneas = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1)], verbose_name="leituras ao mesmo tempo",
        help_text="Quantas importações da mesma pessoa podem estar sendo lidas ao mesmo tempo.",
    )
    abertas_maximo = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1)], verbose_name="importações abertas",
        help_text="Máximo de importações aguardando tipo, lendo ou para revisar, por pessoa.",
    )
    leitura_trava_minutos = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(1)], verbose_name="tempo máximo da leitura (minutos)",
        help_text="Leitura parada há mais tempo que isso vira \"Falhou\" na manutenção.",
    )
    pronta_expira_dias = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1)], verbose_name="prazo para revisar (dias)",
        help_text="Importação para revisar sem mexer há mais tempo que isso vira \"Expirada\".",
    )
    aguardando_expira_horas = models.PositiveSmallIntegerField(
        default=24, validators=[MinValueValidator(1)], verbose_name="prazo para escolher o tipo (horas)",
        help_text="Importação aguardando o tipo há mais tempo que isso vira \"Expirada\".",
    )
    reter_encerradas_dias = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(1)], verbose_name="reter encerradas (dias)",
        help_text="Importações encerradas (confirmadas, descartadas, expiradas ou com falha) são apagadas depois disso.",
    )
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="atualizado em", help_text="Data da última alteração.")

    def __str__(self):
        return "Configuração da importação"

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
        verbose_name = "Configuração da importação"
        verbose_name_plural = "Configuração da importação"
