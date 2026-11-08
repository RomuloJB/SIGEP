"""
Qual arquivo de uma mensagem vai para a importação. Só olha o que o Telegram informa: o
webhook nunca baixa nada (quem baixa é a tarefa, fora da requisição).
"""
from ia.models import ConfiguracaoIA

MEGA = 1024 * 1024
LIMITE_GET_FILE = 20 * MEGA  # acima disso o getFile do Telegram não entrega o arquivo
MIMES_ACEITOS = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}
NOME_DA_FOTO = "foto.jpg"

TIPO_RECUSADO = "Esse tipo de arquivo eu não leio. Envie uma foto, uma imagem (JPG, PNG, WEBP ou HEIC) ou um PDF."
SEM_ARQUIVO = "Não encontrei um arquivo nesta mensagem."


def limite_bytes():
    """O limite da Configuração da IA, nunca acima do que o getFile entrega."""
    return min(ConfiguracaoIA.obter().tamanho_maximo_mb * MEGA, LIMITE_GET_FILE)


def _em_mb(tamanho):
    return "{:.1f}".format(tamanho / MEGA).replace(".", ",")


def _grande_demais(tamanho, limite):
    return "O arquivo tem {} MB e o limite é {} MB. Envie um arquivo menor.".format(_em_mb(tamanho), _em_mb(limite).replace(",0", ""))


def escolher_midia(mensagem):
    """
    Devolve {"file_id", "file_unique_id", "mime", "nome", "tamanho"} do arquivo a importar,
    ou o texto da recusa (str) para mandar à pessoa.
    """
    limite = limite_bytes()
    fotos = mensagem.get("photo")
    if fotos:
        # O Telegram manda a mesma foto em vários tamanhos: vale a maior que caiba no limite
        cabem = [foto for foto in fotos if (foto.get("file_size") or 0) <= limite]
        if not cabem:
            return _grande_demais(max(foto.get("file_size") or 0 for foto in fotos), limite)
        foto = max(cabem, key=lambda foto: (foto.get("width", 0) * foto.get("height", 0), foto.get("file_size") or 0))
        return {
            "file_id": foto["file_id"], "file_unique_id": foto.get("file_unique_id", ""),
            "mime": "image/jpeg", "nome": NOME_DA_FOTO, "tamanho": foto.get("file_size"),
        }

    documento = mensagem.get("document")
    if not documento:
        return SEM_ARQUIVO
    mime = (documento.get("mime_type") or "").lower()
    if mime not in MIMES_ACEITOS:
        return TIPO_RECUSADO
    tamanho = documento.get("file_size")
    if tamanho and tamanho > limite:
        return _grande_demais(tamanho, limite)
    return {
        "file_id": documento["file_id"], "file_unique_id": documento.get("file_unique_id", ""),
        "mime": mime, "nome": documento.get("file_name") or "documento", "tamanho": tamanho,
    }
