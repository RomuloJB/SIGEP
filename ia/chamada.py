"""
Porta de entrada única para a IA: toda chamada a um modelo passa por chamar_ia(),
que confere permissão e cota, repete erros temporários e grava a auditoria.
"""
import hashlib
import json
import logging
import time
from typing import Literal

import pydantic
from django.db import transaction

from . import cota
from .models import ConfiguracaoIA, ConfiguracaoIAUsuario, RequisicaoIA
from .provedores import obter_provedor
from .provedores.base import ErroIA, ErroTemporario, IaIndisponivel, PedidoIA, UsoTokens

logger = logging.getLogger(__name__)


def chamar_ia(*, finalidade, montar_pedido, usuario, origem="site", referencia=None,
              versao_prompt="", arquivo_info=None):
    """
    Faz uma chamada à IA em nome de `usuario` e devolve a RespostaIA.

    montar_pedido(config) -> PedidoIA: só é chamado depois das verificações de cota.
    referencia: qualquer registro do banco ao qual a chamada se refere (ex.: a conversa).
    arquivo_info: {"mime": ..., "tamanho": ..., "hash": ...} do arquivo enviado, se houver.
    Em caso de falha, levanta uma filha de ErroIA (CotaExcedida, IaIndisponivel...).
    """
    config = ConfiguracaoIA.obter()
    dono = cota.dono_da_cota(usuario)
    auditoria = _Auditoria(
        config=config, usuario=usuario, finalidade=finalidade, origem=origem,
        referencia=referencia, versao_prompt=versao_prompt, arquivo_info=arquivo_info,
    )

    # a) IA desligada para o usuário
    if ConfiguracaoIAUsuario.objects.filter(usuario=usuario, ia_habilitada=False).exists():
        erro = IaIndisponivel("A IA está desativada para o seu usuário. Fale com o administrador.")
        auditoria.registrar(tentativa=0, erro=erro)
        raise erro

    # b) teto do sistema
    if cota.teto_do_sistema_atingido():
        erro = IaIndisponivel("A IA atingiu o limite mensal do sistema e está indisponível até o próximo mês.")
        auditoria.registrar(tentativa=0, erro=erro)
        raise erro

    # c) cota do usuário: bloqueia sem chamar o provedor
    try:
        cota.verificar(dono)
    except cota.CotaExcedida as erro:
        auditoria.registrar(tentativa=0, erro=erro)
        raise

    # d) pedido e provedor
    pedido = montar_pedido(config)
    auditoria.contexto_hash = hash_contexto(pedido)
    try:
        provedor = obter_provedor(config)
    except ErroIA as erro:
        auditoria.registrar(tentativa=0, erro=erro)
        raise

    # e) tentativas, repetindo só erro temporário
    total_tentativas = max(config.tentativas, 1)
    for tentativa in range(1, total_tentativas + 1):
        inicio = time.monotonic()
        try:
            resposta = provedor.gerar(pedido)
        except ErroIA as erro:
            auditoria.registrar(tentativa=tentativa, erro=erro, inicio=inicio)
            auditoria.somar_consumo(dono, erro.uso)
            if isinstance(erro, ErroTemporario) and tentativa < total_tentativas:
                time.sleep(1 * tentativa)
                continue
            raise
        except Exception as erro:
            # Falha inesperada do provedor: audita como erro permanente e deixa subir
            auditoria.registrar(tentativa=tentativa, erro=erro, inicio=inicio)
            raise
        auditoria.registrar(tentativa=tentativa, resposta=resposta, inicio=inicio)
        auditoria.somar_consumo(dono, resposta.uso)
        return resposta


class StatusConexao(pydantic.BaseModel):
    status: Literal["ok"]


def testar_conexao(usuario):
    """Pedido mínimo para conferir chave, modelo e rede. Gasta poucos tokens."""
    return chamar_ia(
        finalidade="teste_conexao",
        usuario=usuario,
        montar_pedido=lambda config: PedidoIA(
            instrucoes="Você responde testes de conexão.",
            texto="Teste de conexão: responda com status ok.",
            esquema=StatusConexao,
        ),
    )


def hash_contexto(pedido):
    """SHA-256 do texto enviado (instruções, histórico e mensagem), sem os arquivos."""
    partes = [pedido.instrucoes, [[m.papel, m.texto] for m in pedido.historico], pedido.texto]
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False).encode("utf-8")).hexdigest()


class _Auditoria:
    """Grava RequisicaoIA e ConsumoIA. Nenhuma falha aqui pode derrubar a chamada."""

    def __init__(self, *, config, usuario, finalidade, origem, referencia, versao_prompt, arquivo_info):
        self.config = config
        self.contexto_hash = ""
        arquivo_info = arquivo_info or {}
        self.campos = {
            "usuario": usuario,
            "finalidade": finalidade,
            "origem": origem,
            "referencia": referencia,
            "versao_prompt": versao_prompt,
            "provedor": config.provedor,
            "arquivo_mime": arquivo_info.get("mime", ""),
            "arquivo_tamanho": arquivo_info.get("tamanho"),
            "arquivo_hash": arquivo_info.get("hash", ""),
        }

    def registrar(self, *, tentativa, resposta=None, erro=None, inicio=None):
        try:
            if resposta is not None:
                uso, modelo, motivo_fim, texto = resposta.uso, resposta.modelo, resposta.motivo_fim, resposta.texto
                situacao, mensagem = RequisicaoIA.Situacao.SUCESSO, ""
            elif isinstance(erro, ErroIA):
                uso, modelo, motivo_fim, texto = erro.uso, erro.modelo, erro.motivo_fim, erro.texto_bruto
                situacao, mensagem = erro.situacao, str(erro)
            else:
                uso, modelo, motivo_fim, texto = UsoTokens(), "", "", ""
                situacao, mensagem = RequisicaoIA.Situacao.ERRO_PERMANENTE, repr(erro)
            duracao_ms = int((time.monotonic() - inicio) * 1000) if inicio is not None else 0
            with transaction.atomic():
                RequisicaoIA.objects.create(
                    **self.campos,
                    modelo=modelo or self.config.modelo,
                    tentativa=tentativa,
                    situacao=situacao,
                    tokens_entrada=uso.entrada,
                    tokens_saida=uso.saida,
                    tokens_raciocinio=uso.raciocinio,
                    tokens_total=uso.total,
                    custo_estimado=cota.calcular_custo(uso, self.config),
                    duracao_ms=duracao_ms,
                    motivo_fim=motivo_fim or "",
                    resposta=(texto or "")[:RequisicaoIA.TAMANHO_MAXIMO_RESPOSTA],
                    erro=mensagem[:RequisicaoIA.TAMANHO_MAXIMO_RESPOSTA],
                    contexto_hash=self.contexto_hash,
                )
        except Exception:
            logger.exception("Falha ao gravar a auditoria da IA (finalidade=%s).", self.campos["finalidade"])

    def somar_consumo(self, dono, uso):
        """Soma sempre que houver tokens, mesmo em erro."""
        if not uso.total:
            return
        try:
            with transaction.atomic():
                cota.registrar_consumo(dono, uso, cota.calcular_custo(uso, self.config))
        except Exception:
            logger.exception("Falha ao somar o consumo de IA (finalidade=%s).", self.campos["finalidade"])
