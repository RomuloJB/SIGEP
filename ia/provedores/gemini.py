"""
Provedor Gemini. É o ÚNICO arquivo do projeto que importa google-genai:
o resto do sistema fala só com o contrato de ia/provedores/base.py.
"""
import re

import httpx
import pydantic
from django.views.decorators.debug import sensitive_variables
from google import genai
from google.genai import errors, types

from .base import (
    BloqueioSeguranca, ErroConfiguracao, ErroPermanente, ErroTemporario, ProvedorIA,
    RespostaIA, RespostaInvalida, TempoEsgotado, UsoTokens,
)

# finish_reason / block_reason que significam bloqueio por segurança
MOTIVOS_BLOQUEIO = {"SAFETY", "PROHIBITED_CONTENT"}

# Erro 400 causado pela configuração (chave, modelo ou parâmetro) e não pelo conteúdo do pedido.
# O Gemini responde 400 (e não 401) para chave inválida.
ERRO_400_CONFIGURACAO = re.compile(
    r"api[ _]?key|thinking|temperature|max_?output_?tokens|models/|model .*not (found|supported)",
    re.IGNORECASE,
)


class ProvedorGemini(ProvedorIA):

    @sensitive_variables("chave")
    def __init__(self, config, chave):
        super().__init__(config, chave)
        self.cliente = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(timeout=config.timeout_s * 1000),
        )

    def gerar(self, pedido):
        config = self.config
        try:
            resposta = self.cliente.models.generate_content(
                model=config.modelo,
                contents=self._montar_conteudo(pedido),
                config=self._montar_config(pedido),
            )
        except errors.APIError as erro:
            raise self._traduzir_erro_api(erro) from erro
        except httpx.TimeoutException as erro:
            raise TempoEsgotado(
                f"O Gemini não respondeu em {config.timeout_s} s.", modelo=config.modelo,
            ) from erro
        except httpx.TransportError as erro:
            raise ErroTemporario(
                f"Falha de rede ao chamar o Gemini: {erro}", modelo=config.modelo,
            ) from erro
        return self._ler_resposta(resposta, pedido)

    # ─── Montagem do pedido ───────────────────────────────────────────────────

    def _montar_conteudo(self, pedido):
        conteudo = [
            types.Content(role=mensagem.papel, parts=[types.Part(text=mensagem.texto)])
            for mensagem in pedido.historico
        ]
        partes = [types.Part.from_bytes(data=arquivo.conteudo, mime_type=arquivo.mime) for arquivo in pedido.arquivos]
        if pedido.texto:
            partes.append(types.Part(text=pedido.texto))
        conteudo.append(types.Content(role="user", parts=partes))
        return conteudo

    def _montar_config(self, pedido):
        config = self.config
        opcoes = {
            "system_instruction": pedido.instrucoes or None,
            "temperature": float(config.temperatura),
            "max_output_tokens": config.max_tokens_saida,
        }
        # Vazio = não envia thinking_config e o modelo usa o padrão dele
        if config.nivel_raciocinio:
            opcoes["thinking_config"] = types.ThinkingConfig(thinking_level=config.nivel_raciocinio)
        if pedido.esquema is not None:
            opcoes["response_mime_type"] = "application/json"
            opcoes["response_json_schema"] = esquema_plano(pedido.esquema)
        return types.GenerateContentConfig(**opcoes)

    # ─── Leitura da resposta ──────────────────────────────────────────────────

    def _ler_resposta(self, resposta, pedido):
        uso = ler_uso(resposta.usage_metadata)
        modelo = resposta.model_version or self.config.modelo

        # Pedido bloqueado na entrada: não há candidato nem finish_reason
        bloqueio = resposta.prompt_feedback.block_reason if resposta.prompt_feedback else None
        if bloqueio:
            motivo = _valor(bloqueio)
            raise BloqueioSeguranca(
                f"O Gemini bloqueou o pedido por segurança ({motivo}).",
                uso=uso, modelo=modelo, motivo_fim=motivo,
            )

        candidato = resposta.candidates[0] if resposta.candidates else None
        motivo_fim = _valor(candidato.finish_reason) if candidato and candidato.finish_reason else ""
        texto = resposta.text or ""

        if motivo_fim in MOTIVOS_BLOQUEIO:
            raise BloqueioSeguranca(
                f"O Gemini bloqueou a resposta por segurança ({motivo_fim}).",
                uso=uso, texto_bruto=texto, modelo=modelo, motivo_fim=motivo_fim,
            )
        if motivo_fim == "MAX_TOKENS":
            raise RespostaInvalida(
                "A resposta foi cortada no limite de tokens de saída.",
                uso=uso, texto_bruto=texto, modelo=modelo, motivo_fim=motivo_fim,
            )

        dados = None
        if pedido.esquema is not None:
            try:
                dados = pedido.esquema.model_validate_json(texto)
            except pydantic.ValidationError as erro:
                raise RespostaInvalida(
                    f"A resposta não segue o esquema {pedido.esquema.__name__}: {erro}",
                    uso=uso, texto_bruto=texto, modelo=modelo, motivo_fim=motivo_fim,
                ) from erro

        return RespostaIA(
            texto=texto, dados=dados, uso=uso, modelo=modelo,
            motivo_fim=motivo_fim, id_resposta=resposta.response_id or "",
        )

    def _traduzir_erro_api(self, erro):
        codigo = erro.code or 0
        mensagem = f"Gemini respondeu {codigo} {erro.status or ''}: {erro.message or ''}".strip()
        modelo = self.config.modelo
        if codigo in (401, 403, 404):
            return ErroConfiguracao(mensagem, modelo=modelo)
        if codigo == 400 and ERRO_400_CONFIGURACAO.search(f"{erro.message} {erro.details}"):
            return ErroConfiguracao(mensagem, modelo=modelo)
        if codigo == 429 or codigo >= 500:
            return ErroTemporario(mensagem, modelo=modelo)
        return ErroPermanente(mensagem, modelo=modelo)


def ler_uso(metadados):
    """Converte o usage_metadata do Gemini em UsoTokens ("saida" já inclui o raciocínio)."""
    if metadados is None:
        return UsoTokens()
    raciocinio = metadados.thoughts_token_count or 0
    return UsoTokens(
        entrada=metadados.prompt_token_count or 0,
        saida=(metadados.candidates_token_count or 0) + raciocinio,
        raciocinio=raciocinio,
    )


def esquema_plano(esquema):
    """JSON Schema do model Pydantic com as referências $defs resolvidas no lugar."""
    bruto = esquema.model_json_schema()
    definicoes = bruto.pop("$defs", {})

    def resolver(no, em_uso):
        if isinstance(no, list):
            return [resolver(item, em_uso) for item in no]
        if not isinstance(no, dict):
            return no
        if "$ref" in no:
            nome = no["$ref"].rsplit("/", 1)[-1]
            if nome in em_uso:
                raise ErroPermanente(f"Esquema recursivo não suportado: {nome}.")
            resolvido = resolver(definicoes[nome], em_uso | {nome})
            extras = {chave: valor for chave, valor in no.items() if chave != "$ref"}
            return {**resolvido, **resolver(extras, em_uso)}
        return {chave: resolver(valor, em_uso) for chave, valor in no.items()}

    return resolver(bruto, frozenset())


def _valor(enum_ou_texto):
    return getattr(enum_ou_texto, "value", None) or str(enum_ou_texto)
