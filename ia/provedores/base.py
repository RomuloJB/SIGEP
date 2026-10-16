"""
Contrato neutro entre o sistema e qualquer provedor de IA.

Nada aqui conhece o Gemini: as views e serviços falam só com estas classes,
e cada provedor (ia/provedores/<nome>.py) traduz para a sua biblioteca.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pydantic


@dataclass(frozen=True)
class Arquivo:
    conteudo: bytes
    mime: str
    nome: str = ""


@dataclass(frozen=True)
class MensagemHistorico:
    papel: str  # "user" ou "model"
    texto: str


@dataclass(frozen=True)
class PedidoIA:
    instrucoes: str
    texto: str
    arquivos: tuple = ()
    historico: tuple = ()
    esquema: type[pydantic.BaseModel] | None = None


@dataclass(frozen=True)
class UsoTokens:
    entrada: int = 0
    saida: int = 0  # já inclui os tokens de raciocínio
    raciocinio: int = 0  # só informativo, já contado em "saida"

    @property
    def total(self):
        return self.entrada + self.saida


@dataclass(frozen=True)
class RespostaIA:
    texto: str
    dados: pydantic.BaseModel | None
    uso: UsoTokens
    modelo: str
    motivo_fim: str
    id_resposta: str = ""


# ─── Exceções ─────────────────────────────────────────────────────────────────

class ErroIA(Exception):
    """Erro de uma chamada à IA. "situacao" é o valor gravado na auditoria."""
    situacao = "erro_permanente"

    def __init__(self, mensagem="", *, uso=None, texto_bruto="", modelo="", motivo_fim=""):
        super().__init__(mensagem)
        self.uso = uso or UsoTokens()
        self.texto_bruto = texto_bruto
        self.modelo = modelo
        self.motivo_fim = motivo_fim


class ErroTemporario(ErroIA):
    situacao = "erro_temporario"


class TempoEsgotado(ErroTemporario):
    situacao = "tempo_esgotado"


class ErroPermanente(ErroIA):
    situacao = "erro_permanente"


class RespostaInvalida(ErroIA):
    situacao = "resposta_invalida"


class BloqueioSeguranca(ErroIA):
    situacao = "bloqueada_seguranca"


class ErroConfiguracao(ErroIA):
    situacao = "erro_configuracao"


class IaIndisponivel(ErroIA):
    situacao = "indisponivel"


# ─── Provedor ─────────────────────────────────────────────────────────────────

class ProvedorIA(ABC):
    """
    Base de todo provedor. Recebe a ConfiguracaoIA (modelo, temperatura,
    limites...) e a chave de API, que vem só do .env.
    """

    def __init__(self, config, chave):
        self.config = config

    @abstractmethod
    def gerar(self, pedido: PedidoIA) -> RespostaIA:
        """Envia o pedido ao modelo. Levanta uma filha de ErroIA em caso de falha."""
