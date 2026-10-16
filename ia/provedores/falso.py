"""
Provedor falso para testes: não usa rede nem gasta tokens.

    provedor.programar(texto="olá", uso=UsoTokens(entrada=10, saida=5))
    provedor.programar(erro=TempoEsgotado("demorou"))
    provedor.gerar(pedido)  # devolve "olá"; a próxima chamada levanta TempoEsgotado
"""
from collections import deque

from .base import ProvedorIA, RespostaIA, UsoTokens


class ProvedorFalso(ProvedorIA):

    def __init__(self, config=None, chave=""):
        super().__init__(config, chave)
        self.fila = deque()
        self.pedidos = []  # tudo o que gerar() recebeu, na ordem

    def programar(self, texto="", dados=None, uso=None, erro=None):
        """Enfileira a próxima resposta (ou o erro a levantar)."""
        self.fila.append((texto, dados, uso, erro))

    def gerar(self, pedido):
        self.pedidos.append(pedido)
        modelo = getattr(self.config, "modelo", "") or "falso"
        if not self.fila:
            return RespostaIA(texto="ok", dados=None, uso=UsoTokens(), modelo=modelo, motivo_fim="STOP")
        texto, dados, uso, erro = self.fila.popleft()
        if erro is not None:
            raise erro
        return RespostaIA(texto=texto, dados=dados, uso=uso or UsoTokens(), modelo=modelo, motivo_fim="STOP")
