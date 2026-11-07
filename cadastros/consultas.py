"""
Consultas de leitura que o site e o bot do Telegram usam: a mesma regra nos dois lugares.

Quem entra em qual empresa, quais pedidos cada um enxerga (RN02) e as buscas de
produto. Nada aqui grava no banco.
"""
from django.db.models import Q

from .models import Company, Order, Product

# Abaixo disso o produto aparece no estoque crítico (painel gerencial e bot)
LIMITE_ESTOQUE_BAIXO = 10


def empresas_do_usuario(usuario):
    """Empresas em que o usuário entra: todas para o superusuário; senão, as que ele gerencia ou representa."""
    if usuario.is_superuser:
        return Company.objects.all()
    return Company.objects.filter(Q(manager=usuario) | Q(sales_rep=usuario)).distinct()


def ve_todos_os_pedidos(usuario, empresa):
    """RN02: o gerente da empresa (ou o superusuário) vê todos os pedidos dela; o representante, só os que criou."""
    return usuario.is_superuser or empresa.manager.filter(pk=usuario.pk).exists()


def pedidos_visiveis(usuario, empresa, ve_todos=None):
    """Pedidos da empresa que o usuário pode ver. `ve_todos` evita repetir a consulta de quem já sabe."""
    if ve_todos is None:
        ve_todos = ve_todos_os_pedidos(usuario, empresa)
    pedidos = Order.objects.filter(company=empresa)
    return pedidos if ve_todos else pedidos.filter(created_by=usuario)


def produtos_com_estoque_baixo(empresa):
    """Produtos da empresa com pouco estoque, do menor para o maior."""
    return Product.objects.filter(company=empresa, stock__lte=LIMITE_ESTOQUE_BAIXO).order_by("stock", "name")


def buscar_produtos(empresa, termo):
    """Produtos da empresa pelo nome ou pelo SKU, como nos filtros da listagem de produtos."""
    return Product.objects.filter(Q(name__icontains=termo) | Q(sku__icontains=termo), company=empresa).order_by("name")
