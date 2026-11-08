"""
Importação de documentos pelo bot: receber o arquivo, ler em segundo plano e manter o cartão.

O telegram não conhece nenhum app de domínio aqui: fala só com importacao/services.py, e o
cartão vem de telas.desenhar(), que usa o resumo() e os campos() do importador. O webhook
nunca baixa o arquivo: guarda o file_id e quem baixa é a tarefa.
"""
from html import escape

from importacao import services as importacao_services
from importacao.models import Importacao
from importacao.tarefas import enfileirar, tarefa

from . import arquivos, telas
from .cliente import contexto_do_log, obter_cliente
from .models import AlbumTelegram, ImportacaoTelegram

TAREFA_LER = "telegram.processar_importacao"
AVISO_ALBUM = "📎 Recebi várias fotos de uma vez: vou ler só a primeira. Para importar as outras, envie uma de cada vez."
MSG_DOWNLOAD = "Não consegui baixar o arquivo do Telegram. Tente de novo."
SI = Importacao.Situacao


def _contexto(importacao, chat_id):
    return {"usuario": importacao.criado_por, "telegram_id": chat_id, "tipo": "arquivo"}


def receber_arquivo(mensagem, vinculo, registro):
    """
    Foto ou documento de quem está conectado: abre a importação e mostra o cartão ("Lendo..."
    ou "O que é este documento?"). Chamado pelo roteador, que já cancelou a pergunta em aberto.
    """
    cliente = obter_cliente()
    chat_id = mensagem["chat"]["id"]
    contexto = contexto_do_log(vinculo.telegram_id, vinculo, "arquivo")

    grupo = mensagem.get("media_group_id") or ""
    if grupo:
        # Cada foto do álbum chega num update próprio: só a primeira vira importação
        album, criado = AlbumTelegram.objects.get_or_create(chat_id=chat_id, media_group_id=grupo)
        if not criado:
            if AlbumTelegram.objects.filter(pk=album.pk, avisado=False).update(avisado=True):
                cliente.enviar(chat_id, AVISO_ALBUM, contexto=contexto)
            return

    midia = arquivos.escolher_midia(mensagem)
    if isinstance(midia, str):
        cliente.enviar(chat_id, escape(midia, quote=False), contexto=contexto)
        return
    try:
        importacao = importacao_services.iniciar_importacao(
            vinculo.usuario, Importacao.Origem.TELEGRAM, observacao=mensagem.get("caption", ""),
            arquivo_nome=midia["nome"], arquivo_mime=midia["mime"], arquivo_tamanho=midia["tamanho"],
        )
    except importacao_services.ImportacaoRecusada as erro:
        cliente.enviar(chat_id, escape(str(erro), quote=False), contexto=contexto)
        return

    ImportacaoTelegram.objects.create(
        importacao=importacao, chat_id=chat_id, mensagem_usuario_id=mensagem.get("message_id"),
        file_id=midia["file_id"], file_unique_id=midia["file_unique_id"], media_group_id=grupo,
    )
    enviar_cartao(importacao, chat_id)
    if importacao.situacao == SI.PROCESSANDO:
        agendar(importacao)


def agendar(importacao):
    """Põe a leitura na fila. Se a fila recusar, a importação vira "falhou" e o cartão mostra "Tentar de novo"."""
    enfileirar(
        TAREFA_LER, importacao_id=importacao.pk,
        ao_recusar=lambda: importacao_services.marcar_falha(importacao, importacao_services.MSG_FILA),
    )


@tarefa(TAREFA_LER)
def processar_importacao(importacao_id):
    """Baixa o arquivo (parando no limite) e lê. O cartão é redesenhado pelo sinal (telegram/signals.py)."""
    vinculo = ImportacaoTelegram.objects.select_related("importacao__criado_por").filter(importacao_id=importacao_id).first()
    if vinculo is None or vinculo.importacao.situacao != SI.PROCESSANDO:
        return
    importacao = vinculo.importacao
    conteudo = None
    if vinculo.file_id:
        conteudo = obter_cliente().baixar_arquivo(
            vinculo.file_id, arquivos.limite_bytes(), contexto=_contexto(importacao, vinculo.chat_id),
        )
    if conteudo is None:
        importacao_services.marcar_falha(importacao, MSG_DOWNLOAD)
        return
    importacao_services.processar_importacao(importacao, conteudo, importacao.arquivo_mime)


# ─── Cartão ───────────────────────────────────────────────────────────────────

def guardar_cartao(importacao, chat_id, mensagem):
    """Anota qual mensagem é o cartão vivo da importação: é ela que o sinal edita."""
    if isinstance(mensagem, dict) and mensagem.get("message_id"):
        ImportacaoTelegram.objects.update_or_create(
            importacao=importacao, defaults={"chat_id": chat_id, "mensagem_bot_id": mensagem["message_id"]},
        )


def enviar_cartao(importacao, chat_id, nota=""):
    tela = telas.desenhar(importacao, nota)
    enviada = obter_cliente().enviar(chat_id, tela.texto, tela.teclado, contexto=_contexto(importacao, chat_id))
    guardar_cartao(importacao, chat_id, enviada)


def atualizar_cartao(importacao, nota=""):
    """Edita o cartão vivo; se não der (apagado, antigo demais), manda um novo no fim do chat."""
    vinculo = ImportacaoTelegram.objects.filter(importacao=importacao).first()
    if vinculo is None or not vinculo.mensagem_bot_id:
        return
    tela = telas.desenhar(importacao, nota)
    contexto = _contexto(importacao, vinculo.chat_id)
    if obter_cliente().editar(vinculo.chat_id, vinculo.mensagem_bot_id, tela.texto, tela.teclado, contexto=contexto) is None:
        enviar_cartao(importacao, vinculo.chat_id, nota)


def reabrir_cartao(importacao, chat_id):
    """Manda o cartão de novo no fim do chat (onde a pessoa está olhando) e apaga o antigo."""
    vinculo = ImportacaoTelegram.objects.filter(importacao=importacao).first()
    antigo = vinculo.mensagem_bot_id if vinculo and vinculo.chat_id == chat_id else None
    enviar_cartao(importacao, chat_id)
    if antigo:
        obter_cliente().apagar(chat_id, antigo, contexto=_contexto(importacao, chat_id))
