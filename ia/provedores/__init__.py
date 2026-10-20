"""
Escolha do provedor de IA a partir da ConfiguracaoIA.

A chave vem só do .env (GEMINI_API_KEY, carregado por python-dotenv no settings.py).
O provedor fica em cache por (provedor, atualizado_em): ao salvar a configuração
na tela, o próximo uso cria um cliente novo.
"""
import os
import threading

from django.utils.module_loading import import_string
from django.views.decorators.debug import sensitive_variables

from .base import ErroConfiguracao

PROVEDORES = {
    "gemini": "ia.provedores.gemini.ProvedorGemini",
    "falso": "ia.provedores.falso.ProvedorFalso",
}

_cache = {}
_trava = threading.Lock()


@sensitive_variables("chave")
def obter_provedor(config):
    chave_cache = (config.provedor, config.atualizado_em)
    with _trava:
        provedor = _cache.get(chave_cache)
        if provedor is not None:
            return provedor

        caminho = PROVEDORES.get(config.provedor)
        if caminho is None:
            raise ErroConfiguracao(f"Provedor de IA desconhecido: {config.provedor!r}.")
        chave = os.getenv("GEMINI_API_KEY", "").strip()
        if config.provedor == "gemini" and not chave:
            raise ErroConfiguracao(
                "GEMINI_API_KEY não configurada: inclua a chave no arquivo .env da raiz "
                "do projeto (ao lado de manage.py) e reinicie o servidor."
            )
        provedor = import_string(caminho)(config, chave)
        # Só a configuração atual interessa: descarta clientes de versões anteriores
        _cache.clear()
        _cache[chave_cache] = provedor
        return provedor
