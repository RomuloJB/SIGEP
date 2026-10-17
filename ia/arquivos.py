"""
Preparo de arquivos antes de enviá-los à IA: confere tamanho e tipo, limita páginas
de PDF e reduz imagens. As mensagens de ArquivoInvalido podem ir direto ao usuário.
"""
import hashlib
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from .models import ConfiguracaoIA

# Acima disso o Pillow recusa a imagem (proteção contra "bomba de descompressão")
Image.MAX_IMAGE_PIXELS = 50_000_000

MIME_PDF = "application/pdf"
MIME_JPEG = "image/jpeg"


class ArquivoInvalido(Exception):
    """Arquivo recusado; a mensagem já está pronta para mostrar ao usuário."""


def preparar_arquivo(conteudo, mime, lado_maximo=2048):
    """Devolve (bytes, mime) prontos para enviar à IA ou levanta ArquivoInvalido."""
    config = ConfiguracaoIA.obter()
    mime = (mime or "").lower()

    if not conteudo:
        raise ArquivoInvalido("O arquivo está vazio.")
    if len(conteudo) > config.tamanho_maximo_mb * 1024 * 1024:
        raise ArquivoInvalido("O arquivo passa do tamanho máximo permitido de {} MB.".format(config.tamanho_maximo_mb))

    if mime == MIME_PDF or conteudo.startswith(b"%PDF-"):
        return _preparar_pdf(conteudo, config), MIME_PDF
    if mime.startswith("image/"):
        return _preparar_imagem(conteudo, lado_maximo), MIME_JPEG
    raise ArquivoInvalido("Tipo de arquivo não aceito. Envie uma imagem (JPG, PNG...) ou um PDF.")


def hash_arquivo(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def _preparar_pdf(conteudo, config):
    try:
        leitor = PdfReader(BytesIO(conteudo))
        if leitor.is_encrypted:
            raise ArquivoInvalido("O PDF está protegido por senha. Envie uma versão sem senha.")
        paginas = len(leitor.pages)
    except ArquivoInvalido:
        raise
    except Exception:
        raise ArquivoInvalido("Não foi possível ler o PDF. Verifique se o arquivo não está corrompido.")
    if paginas > config.pdf_max_paginas:
        raise ArquivoInvalido(
            "O PDF tem {} páginas; o máximo permitido é {}.".format(paginas, config.pdf_max_paginas)
        )
    return conteudo


def _preparar_imagem(conteudo, lado_maximo):
    try:
        imagem = Image.open(BytesIO(conteudo))
        if imagem.width * imagem.height > Image.MAX_IMAGE_PIXELS:
            raise ArquivoInvalido("A imagem tem resolução grande demais. Envie uma imagem menor.")
        imagem = ImageOps.exif_transpose(imagem)
        imagem = _para_rgb(imagem)
        imagem.thumbnail((lado_maximo, lado_maximo))
        saida = BytesIO()
        imagem.save(saida, format="JPEG", quality=85)
    except ArquivoInvalido:
        raise
    except Image.DecompressionBombError:
        raise ArquivoInvalido("A imagem tem resolução grande demais. Envie uma imagem menor.")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ArquivoInvalido("Não foi possível ler a imagem. Verifique se o arquivo não está corrompido.")
    return saida.getvalue()


def _para_rgb(imagem):
    """Converte para RGB; partes transparentes viram fundo branco (e não preto)."""
    if imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info):
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, (255, 255, 255))
        fundo.paste(imagem, mask=imagem.getchannel("A"))
        return fundo
    return imagem.convert("RGB")
