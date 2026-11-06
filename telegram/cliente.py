"""
Único módulo que fala com a API do Telegram. O resto do bot usa obter_cliente().

Três garantias: nunca levanta exceção (falha devolve None, porque um aviso que não saiu
não pode desfazer o que já foi gravado), o token não aparece em nenhum log e toda chamada
fica registrada no MensagemTelegram.
"""
import json
import logging
import time
from collections import defaultdict, deque
from urllib.parse import quote

import httpx
from django.conf import settings
from django.db import transaction

from .models import MensagemTelegram

logger = logging.getLogger(__name__)

# Em nível INFO, o httpx escreve a URL inteira da requisição, e a URL traz o token.
logging.getLogger("httpx").setLevel(logging.WARNING)

API_URL = "https://api.telegram.org"
MASCARA = "***"
MENSAGEM_NAO_MODIFICADA = "message is not modified"
METODO_DOWNLOAD = "downloadFile"  # não é método da API: só o nome do download no log
STATUS_FORA_DO_LOG_DE_ERROS = (403, 429)  # 403 = a pessoa bloqueou o bot; não é bug

LIMITE_CALLBACK_BYTES = 64
LIMITE_ROTULO = 40
LIMITE_RESPOSTA_BOTAO = 200


def mascarar(texto):
    """Troca o token e o segredo do webhook por *** em qualquer texto."""
    texto = str(texto)
    for segredo in (settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_WEBHOOK_SECRET):
        if segredo:
            texto = texto.replace(segredo, MASCARA).replace(quote(segredo, safe=""), MASCARA)
    return texto


def _rotulo(texto):
    return texto[:LIMITE_ROTULO - 1] + "…" if len(texto) > LIMITE_ROTULO else texto


def botao(texto, callback_data):
    """Monta um botão inline. Dados acima do limite são erro de programação: levanta ValueError."""
    if len(callback_data.encode("utf-8")) > LIMITE_CALLBACK_BYTES:
        raise ValueError("callback_data acima de {} bytes: {!r}".format(LIMITE_CALLBACK_BYTES, callback_data))
    return {"text": _rotulo(texto), "callback_data": callback_data}


def botao_link(texto, url):
    """Monta um botão inline que abre um endereço."""
    return {"text": _rotulo(texto), "url": url}


def contexto_do_log(telegram_id, vinculo=None, tipo="comando"):
    """Contexto de uma chamada feita em nome desta pessoa."""
    return {"usuario": vinculo.usuario if vinculo else None, "telegram_id": telegram_id, "tipo": tipo}


def _marcacao(teclado):
    """teclado: lista de linhas, cada linha uma lista de botao()."""
    return None if teclado is None else {"inline_keyboard": teclado}


class ClienteBase:
    """
    Atalhos da API, iguais no cliente real e no falso.
    contexto: dicionário opcional para o log, com usuario, telegram_id e tipo.
    """

    def chamar(self, metodo, contexto=None, **params):
        raise NotImplementedError

    def _baixar(self, caminho, limite_bytes, contexto=None):
        raise NotImplementedError

    def enviar(self, chat_id, texto, teclado=None, contexto=None):
        return self.chamar(
            "sendMessage", contexto=contexto, chat_id=chat_id, text=texto,
            parse_mode="HTML", reply_markup=_marcacao(teclado),
        )

    def editar(self, chat_id, mensagem_id, texto, teclado=None, contexto=None):
        return self.chamar(
            "editMessageText", contexto=contexto, chat_id=chat_id, message_id=mensagem_id, text=texto,
            parse_mode="HTML", reply_markup=_marcacao(teclado),
        )

    def apagar(self, chat_id, mensagem_id, contexto=None):
        return self.chamar("deleteMessage", contexto=contexto, chat_id=chat_id, message_id=mensagem_id)

    def responder_botao(self, callback_id, texto=None, alerta=False, contexto=None):
        return self.chamar(
            "answerCallbackQuery", contexto=contexto, callback_query_id=callback_id,
            text=texto[:LIMITE_RESPOSTA_BOTAO] if texto else None, show_alert=alerta,
        )

    def baixar_arquivo(self, file_id, limite_bytes, contexto=None):
        """Devolve os bytes do arquivo, ou None se falhar ou passar de limite_bytes."""
        info = self.chamar("getFile", contexto=contexto, file_id=file_id)
        caminho = info.get("file_path") if isinstance(info, dict) else None
        if not caminho:
            return None
        return self._baixar(caminho, limite_bytes, contexto)


class ClienteTelegram(ClienteBase):

    def __init__(self, transporte=None):
        # transporte: httpx.MockTransport nos testes do próprio cliente
        self._http = httpx.Client(timeout=settings.TELEGRAM_TIMEOUT_S, transport=transporte)

    def chamar(self, metodo, contexto=None, **params):
        """Faz a chamada e devolve o `result` da API (True se não houver), ou None em caso de falha."""
        params = {nome: valor for nome, valor in params.items() if valor is not None}
        inicio = time.monotonic()
        status, corpo, erro = None, {}, ""
        try:
            status, corpo = self._postar(metodo, params)
            espera = self._espera_do_429(status, corpo)
            if espera is not None:
                time.sleep(espera)
                status, corpo = self._postar(metodo, params)
        except Exception as falha:
            erro = _descrever(falha)

        descricao = str(corpo.get("description") or "")
        if corpo.get("ok"):
            resultado = corpo.get("result", True)
        elif MENSAGEM_NAO_MODIFICADA in descricao:
            resultado = True  # a mensagem já está como deveria: para quem chamou, deu certo
        else:
            resultado = None
            erro = erro or descricao or "HTTP {}".format(status)

        self._concluir(metodo, contexto, inicio, status, erro, params, resultado)
        return resultado

    def _baixar(self, caminho, limite_bytes, contexto=None):
        """Baixa em streaming e para assim que passar do limite, sem ler o resto do arquivo."""
        inicio = time.monotonic()
        status, erro, conteudo = None, "", bytearray()
        try:
            with self._http.stream("GET", "{}/file/bot{}/{}".format(API_URL, self._token(), caminho)) as resposta:
                status = resposta.status_code
                if status != 200:
                    erro = "HTTP {}".format(status)
                else:
                    for pedaco in resposta.iter_bytes():
                        conteudo += pedaco
                        if len(conteudo) > limite_bytes:
                            erro = "Arquivo acima do limite de {} bytes.".format(limite_bytes)
                            break
        except Exception as falha:
            erro = _descrever(falha)

        self._concluir(METODO_DOWNLOAD, contexto, inicio, status, erro)
        return None if erro else bytes(conteudo)

    def _postar(self, metodo, params):
        resposta = self._http.post("{}/bot{}/{}".format(API_URL, self._token(), metodo), json=params)
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = None  # ex.: página de erro de um proxy no meio do caminho
        return resposta.status_code, corpo if isinstance(corpo, dict) else {}

    @staticmethod
    def _token():
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env.")
        return settings.TELEGRAM_BOT_TOKEN

    @staticmethod
    def _espera_do_429(status, corpo):
        """Segundos a esperar antes de repetir a chamada, ou None se não for para repetir."""
        if status != 429:
            return None
        espera = (corpo.get("parameters") or {}).get("retry_after")
        if isinstance(espera, (int, float)) and espera <= settings.TELEGRAM_RETRY_MAX_S:
            return espera
        return None

    def _concluir(self, metodo, contexto, inicio, status, erro, params=None, resultado=None):
        erro = mascarar(erro)
        self._registrar(metodo, contexto or {}, inicio, status, erro, params or {}, resultado)
        if erro:
            avisar = logger.info if status in STATUS_FORA_DO_LOG_DE_ERROS else logger.error
            avisar("Telegram %s falhou (HTTP %s): %s", metodo, status, erro)

    def _registrar(self, metodo, contexto, inicio, status, erro, params, resultado):
        """Grava a saída no log. Nenhuma falha aqui pode derrubar a chamada."""
        try:
            usuario = contexto.get("usuario")
            mensagem_id = resultado.get("message_id") if isinstance(resultado, dict) else None
            with transaction.atomic():
                MensagemTelegram.objects.create(
                    direcao=MensagemTelegram.Direcao.SAIDA,
                    tipo=contexto.get("tipo", ""),
                    metodo_api=metodo,
                    telegram_id=contexto.get("telegram_id"),
                    chat_id=params.get("chat_id"),
                    mensagem_id=mensagem_id or params.get("message_id"),
                    usuario=usuario,
                    texto=mascarar(params.get("text", "")),
                    # JSON só de quem está conectado
                    conteudo=json.loads(mascarar(json.dumps(params, ensure_ascii=False))) if usuario else None,
                    situacao=MensagemTelegram.Situacao.FALHOU if erro else MensagemTelegram.Situacao.ENVIADA,
                    status_http=status,
                    erro=erro,
                    duracao_ms=int((time.monotonic() - inicio) * 1000),
                )
        except Exception:
            logger.exception("Falha ao gravar o log do Telegram (método %s).", metodo)


class ClienteFalso(ClienteBase):
    """
    Para os testes: não usa rede e guarda tudo o que o bot enviaria.

        cliente = obter_cliente()
        cliente.limpar()                         # no setUp: o cliente é o mesmo no processo todo
        cliente.programar("sendMessage", None)   # a próxima chamada falha
        cliente.arquivos["abc"] = b"..."         # conteúdo de baixar_arquivo("abc", ...)
        cliente.mensagens                        # [{"metodo": "sendMessage", "chat_id": 1, ...}]
    """

    def __init__(self):
        self.limpar()

    def limpar(self):
        self.mensagens = []
        self.arquivos = {}
        self._programados = defaultdict(deque)
        self._ultimo_id = 0

    def programar(self, metodo, resultado):
        """Define o retorno da próxima chamada a `metodo`. None simula uma falha."""
        self._programados[metodo].append(resultado)

    def chamar(self, metodo, contexto=None, **params):
        params = {nome: valor for nome, valor in params.items() if valor is not None}
        self.mensagens.append({"metodo": metodo, **params})
        if self._programados[metodo]:
            return self._programados[metodo].popleft()
        if metodo == "sendMessage":
            self._ultimo_id += 1
            return {"message_id": self._ultimo_id, "chat": {"id": params.get("chat_id")}}
        if metodo == "getFile":
            return {"file_path": params["file_id"]}
        return True

    def _baixar(self, caminho, limite_bytes, contexto=None):
        conteudo = self.arquivos.get(caminho)
        if conteudo is None or len(conteudo) > limite_bytes:
            return None
        return conteudo


def _descrever(falha):
    # Vai sempre por mascarar(): a mensagem de uma exceção do httpx pode trazer a URL
    return "{}: {}".format(type(falha).__name__, falha)


_cliente = None


def obter_cliente():
    """Devolve o cliente do processo, que reaproveita a conexão: o falso durante os testes."""
    global _cliente
    if _cliente is None:
        _cliente = ClienteFalso() if settings.EM_TESTES else ClienteTelegram()
    return _cliente
