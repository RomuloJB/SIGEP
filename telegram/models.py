import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


class VinculoTelegram(models.Model):
    """Liga um usuário do site a uma pessoa no Telegram. O vínculo é pela pessoa (telegram_id)."""
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram",
        verbose_name="usuário", help_text="Usuário do site ligado a esta pessoa no Telegram.",
    )
    telegram_id = models.BigIntegerField(
        unique=True, verbose_name="id no Telegram",
        help_text="Número que identifica a pessoa no Telegram. Passa de 2 bilhões, por isso o campo é grande.",
    )
    chat_id = models.BigIntegerField(
        verbose_name="id da conversa",
        help_text="Conversa com o bot, para onde vão as respostas. É atualizado a cada mensagem.",
    )
    username = models.CharField(
        max_length=64, blank=True, verbose_name="username",
        help_text="Username no Telegram, sem o @. Exemplo: maria_silva",
    )
    nome = models.CharField(
        max_length=150, blank=True, verbose_name="nome",
        help_text="Nome de exibição no Telegram. Exemplo: Maria Silva",
    )
    vinculado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="vinculado em", help_text="Momento em que a conexão foi feita.",
    )
    ultimo_uso = models.DateTimeField(
        null=True, blank=True, verbose_name="último uso", help_text="Última vez que a pessoa usou o bot.",
    )
    empresa = models.ForeignKey(
        "cadastros.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="empresa no bot",
        help_text="Empresa usada nos comandos do bot, escolhida com /empresa. Com uma empresa só, ela é escolhida sozinha.",
    )

    def __str__(self):
        return "{} ({})".format(self.usuario, self.username or self.telegram_id)

    class Meta:
        verbose_name = "Vínculo com o Telegram"
        verbose_name_plural = "Vínculos com o Telegram"


class CodigoVinculoTelegram(models.Model):
    """Código de uso único do link t.me/<bot>?start=CODIGO. No banco fica só o hash."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codigos_telegram",
        verbose_name="usuário", help_text="Usuário que pediu a conexão.",
    )
    token_hash = models.CharField(
        max_length=64, unique=True, verbose_name="hash do código",
        help_text="SHA-256 do código. O código em si não é guardado.",
    )
    expira_em = models.DateTimeField(verbose_name="expira em", help_text="Depois deste momento o código não vale mais.")
    usado_em = models.DateTimeField(
        null=True, blank=True, verbose_name="usado em", help_text="Momento em que o código criou o vínculo.",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Momento em que o código foi gerado.")

    def __str__(self):
        return "Código de {} (expira em {})".format(self.usuario, self.expira_em)

    @staticmethod
    def calcular_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def emitir(cls, usuario):
        """Invalida os códigos abertos do usuário e devolve um novo, que não fica guardado."""
        agora = timezone.now()
        token = secrets.token_urlsafe(24)
        with transaction.atomic():
            cls.objects.filter(usuario=usuario, usado_em__isnull=True, expira_em__gt=agora).update(expira_em=agora)
            cls.objects.create(
                usuario=usuario,
                token_hash=cls.calcular_hash(token),
                expira_em=agora + timedelta(minutes=settings.TELEGRAM_CODIGO_VALIDADE_MIN),
            )
        return token

    @classmethod
    def buscar_valido(cls, token):
        """Devolve o código ainda não usado e dentro da validade, ou None."""
        if not token:
            return None
        return cls.objects.select_related("usuario").filter(
            token_hash=cls.calcular_hash(token), usado_em__isnull=True, expira_em__gt=timezone.now(),
        ).first()

    class Meta:
        verbose_name = "Código de vínculo com o Telegram"
        verbose_name_plural = "Códigos de vínculo com o Telegram"


class MensagemTelegram(models.Model):
    """Log de tudo o que entra e sai do bot. Nunca guarda o token nem o segredo do webhook."""

    class Direcao(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    class Situacao(models.TextChoices):
        RECEBIDA = "recebida", "Recebida"
        PROCESSADA = "processada", "Processada"
        IGNORADA = "ignorada", "Ignorada"
        ERRO = "erro", "Erro"
        ENVIADA = "enviada", "Enviada"
        FALHOU = "falhou", "Falhou"

    direcao = models.CharField(
        max_length=10, choices=Direcao.choices, verbose_name="direção",
        help_text="Entrada: update recebido do Telegram. Saída: chamada feita à API do Telegram.",
    )
    tipo = models.CharField(
        max_length=30, blank=True, verbose_name="tipo",
        help_text="Tipo do que foi recebido. Exemplos: comando, botao, arquivo, texto",
    )
    update_id = models.BigIntegerField(
        null=True, blank=True, unique=True, verbose_name="id do update",
        help_text="Identificador do update no Telegram. É único para não processar o mesmo update duas vezes.",
    )
    metodo_api = models.CharField(
        max_length=40, blank=True, verbose_name="método da API",
        help_text="Método chamado, nas saídas. Exemplo: sendMessage",
    )
    telegram_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="id no Telegram", help_text="Pessoa que enviou ou que vai receber.",
    )
    chat_id = models.BigIntegerField(null=True, blank=True, verbose_name="id da conversa", help_text="Conversa envolvida.")
    mensagem_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="id da mensagem", help_text="Identificador da mensagem dentro da conversa.",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mensagens_telegram", verbose_name="usuário", help_text="Usuário do site, se a pessoa estiver conectada.",
    )
    texto = models.TextField(blank=True, verbose_name="texto", help_text="Texto da mensagem, com o código do /start mascarado.")
    conteudo = models.JSONField(
        null=True, blank=True, verbose_name="conteúdo",
        help_text="JSON completo, guardado só para quem está conectado.",
    )
    situacao = models.CharField(max_length=15, choices=Situacao.choices, verbose_name="situação", help_text="Resultado do registro.")
    status_http = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="status HTTP", help_text="Status devolvido pela API do Telegram, nas saídas.",
    )
    erro = models.TextField(blank=True, verbose_name="erro", help_text="Mensagem de erro, com o token mascarado.")
    duracao_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="duração (ms)", help_text="Tempo gasto em milissegundos.")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Momento do registro.")

    def __str__(self):
        return "{} | {} | {} | {}".format(
            self.criado_em, self.get_direcao_display(), self.metodo_api or self.tipo, self.get_situacao_display(),
        )

    class Meta:
        verbose_name = "Mensagem do Telegram"
        verbose_name_plural = "Mensagens do Telegram"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["usuario", "-criado_em"], name="tg_msg_usuario_criado"),
            models.Index(fields=["chat_id", "-criado_em"], name="tg_msg_chat_criado"),
            models.Index(fields=["situacao"], name="tg_msg_situacao"),
        ]


class ConfiguracaoTelegram(models.Model):
    """
    Configuração única (pk=1) dos limites e da retenção do bot.
    Token e segredo do webhook NÃO ficam aqui: vêm só do .env.
    """
    CHAVE_CACHE = "telegram:configuracao"
    SEGUNDOS_CACHE = 30

    # Quem está conectado
    mensagens_por_minuto = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1)], verbose_name="mensagens por minuto",
        help_text="Acima disso, a pessoa conectada recebe um aviso e o bot faz uma pausa.",
    )
    arquivos_por_minuto = models.PositiveSmallIntegerField(
        default=4, validators=[MinValueValidator(1)], verbose_name="arquivos por minuto",
        help_text="Acima disso, os arquivos extras da pessoa conectada são recusados.",
    )
    bloqueio_minutos = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1)], verbose_name="pausa (minutos)",
        help_text="Duração da pausa de quem passou do limite de mensagens.",
    )

    # Quem não está conectado
    desconhecido_mensagens_por_minuto = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1)], verbose_name="mensagens por minuto (não conectado)",
        help_text="Acima disso, quem não está conectado passa a ser ignorado.",
    )
    desconhecido_bloqueio_minutos = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(1)], verbose_name="tempo ignorado (minutos)",
        help_text="Por quanto tempo quem não está conectado fica sendo ignorado.",
    )
    desconhecido_aviso_horas = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(1)], verbose_name="intervalo do aviso (horas)",
        help_text="De quanto em quanto tempo quem não está conectado recebe o aviso para conectar o usuário.",
    )

    # Conversa
    espera_minutos = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(1)], verbose_name="prazo da pergunta (minutos)",
        help_text="Por quanto tempo o bot espera a resposta de uma pergunta. Depois disso, o texto não vale mais como resposta.",
    )

    # Retenção do log
    reter_conteudo_dias = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1)], verbose_name="reter JSON (dias)",
        help_text="Depois deste prazo, o JSON completo das mensagens é apagado.",
    )
    reter_mensagens_dias = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(1)], verbose_name="reter mensagens (dias)",
        help_text="Depois deste prazo, as mensagens são apagadas do log.",
    )

    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="atualizado em", help_text="Data da última alteração.")

    def __str__(self):
        return "Configuração do Telegram"

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
        verbose_name = "Configuração do Telegram"
        verbose_name_plural = "Configuração do Telegram"


class LimiteTelegram(models.Model):
    """Contador por remetente, no banco porque o App Engine pode ter várias instâncias."""
    telegram_id = models.BigIntegerField(unique=True, verbose_name="id no Telegram", help_text="Pessoa que está sendo contada.")
    janela_inicio = models.DateTimeField(
        null=True, blank=True, verbose_name="início da janela", help_text="Início do minuto em que as mensagens estão sendo contadas.",
    )
    mensagens = models.PositiveIntegerField(default=0, verbose_name="mensagens", help_text="Mensagens na janela atual.")
    arquivos = models.PositiveIntegerField(default=0, verbose_name="arquivos", help_text="Arquivos na janela atual.")
    avisou_arquivos = models.BooleanField(
        default=False, verbose_name="avisou dos arquivos", help_text="Se o aviso de excesso de arquivos já foi dado nesta janela.",
    )
    bloqueado_ate = models.DateTimeField(
        null=True, blank=True, verbose_name="bloqueado até", help_text="Até quando as mensagens desta pessoa são descartadas.",
    )
    aviso_em = models.DateTimeField(
        null=True, blank=True, verbose_name="último aviso", help_text="Última vez que a pessoa recebeu um aviso de limite ou de conexão.",
    )
    erro_avisado_em = models.DateTimeField(
        null=True, blank=True, verbose_name="último aviso de erro", help_text="Última vez que a pessoa recebeu \"Algo deu errado\".",
    )
    total = models.PositiveBigIntegerField(default=0, verbose_name="total", help_text="Mensagens recebidas desde o início.")
    descartadas = models.PositiveBigIntegerField(default=0, verbose_name="descartadas", help_text="Mensagens ignoradas pelos limites.")
    primeira_vez = models.DateTimeField(auto_now_add=True, verbose_name="primeira vez", help_text="Primeira mensagem recebida.")
    ultima_vez = models.DateTimeField(auto_now=True, verbose_name="última vez", help_text="Última mensagem recebida.")

    def __str__(self):
        return "Limite de {}".format(self.telegram_id)

    @property
    def bloqueado(self):
        return self.bloqueado_ate is not None and self.bloqueado_ate > timezone.now()

    class Meta:
        verbose_name = "Limite do Telegram"
        verbose_name_plural = "Limites do Telegram"


class EsperaTelegram(models.Model):
    """A "memória" de que o bot fez uma pergunta e aguarda um texto. Uma por pessoa."""
    vinculo = models.OneToOneField(
        VinculoTelegram, on_delete=models.CASCADE, related_name="espera", verbose_name="vínculo",
        help_text="Pessoa de quem o bot espera a resposta.",
    )
    campo = models.CharField(max_length=20, verbose_name="campo", help_text="Código curto do que foi perguntado. Exemplo: data")
    referencia_tipo = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="tipo da referência",
        help_text="Tipo do registro que a resposta vai alterar.",
    )
    referencia_id = models.PositiveBigIntegerField(
        null=True, blank=True, verbose_name="id da referência", help_text="Id do registro que a resposta vai alterar.",
    )
    referencia = GenericForeignKey("referencia_tipo", "referencia_id")
    mensagem_pergunta_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="id da pergunta", help_text="Mensagem da pergunta, apagada depois da resposta.",
    )
    desde = models.DateTimeField(
        default=timezone.now, verbose_name="desde", help_text="Momento da pergunta, de onde conta o prazo da espera.",
    )

    def __str__(self):
        return "Espera de {} ({})".format(self.vinculo, self.campo)

    class Meta:
        verbose_name = "Espera do Telegram"
        verbose_name_plural = "Esperas do Telegram"


class ImportacaoTelegram(models.Model):
    """Liga uma importação à conversa: o arquivo no Telegram e a mensagem do cartão, que é editada a cada mudança."""
    importacao = models.OneToOneField(
        "importacao.Importacao", on_delete=models.CASCADE, related_name="telegram", verbose_name="importação",
        help_text="Importação que este cartão mostra.",
    )
    chat_id = models.BigIntegerField(verbose_name="id da conversa", help_text="Conversa onde está o cartão.")
    mensagem_usuario_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="mensagem da pessoa", help_text="Mensagem com o arquivo enviado.",
    )
    mensagem_bot_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="mensagem do cartão", help_text="Mensagem do bot editada a cada mudança da importação.",
    )
    file_id = models.CharField(
        max_length=255, blank=True, verbose_name="file_id",
        help_text="Identificador do arquivo no Telegram, para baixar de novo numa nova tentativa. Vazio se veio do site.",
    )
    file_unique_id = models.CharField(max_length=100, blank=True, verbose_name="file_unique_id", help_text="Identificador fixo do arquivo no Telegram.")
    media_group_id = models.CharField(max_length=64, blank=True, verbose_name="álbum", help_text="Álbum de fotos de onde o arquivo veio, se houver.")

    def __str__(self):
        return "Cartão da importação #{}".format(self.importacao_id)

    class Meta:
        verbose_name = "Importação pelo Telegram"
        verbose_name_plural = "Importações pelo Telegram"


class AlbumTelegram(models.Model):
    """Um álbum (várias fotos de uma vez) vira uma importação só e um aviso único."""
    chat_id = models.BigIntegerField(verbose_name="id da conversa", help_text="Conversa onde o álbum chegou.")
    media_group_id = models.CharField(max_length=64, verbose_name="álbum", help_text="Identificador do álbum no Telegram.")
    avisado = models.BooleanField(
        default=False, verbose_name="avisado", help_text="Se a pessoa já foi avisada de que só a primeira foto é lida.",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="criado em", help_text="Quando a primeira foto chegou.")

    def __str__(self):
        return "Álbum {} na conversa {}".format(self.media_group_id, self.chat_id)

    class Meta:
        verbose_name = "Álbum do Telegram"
        verbose_name_plural = "Álbuns do Telegram"
        constraints = [
            models.UniqueConstraint(fields=["chat_id", "media_group_id"], name="tg_album_unico"),
        ]
