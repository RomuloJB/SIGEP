from django.db import models

from .masks import format_cnpj, format_cpf_cnpj

# Create your models here.

class User_Profile(models.Model):
    name = models.CharField(max_length=100, verbose_name="nome", help_text="Nome completo. Exemplo: Maria da Silva")
    phone = models.CharField(max_length=11, verbose_name="telefone", help_text="Apenas números, com DDD. Exemplo: 41999999999")
    cpf = models.CharField(max_length=14, verbose_name="CPF", help_text="Formato: 000.000.000-00")
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile', verbose_name="usuário")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"
        ordering = ['name']


class BaseClass(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="atualizado em")
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='%(app_label)s_%(class)s_created_by', verbose_name="criado por")
    
    class Meta: abstract = True


class Company(BaseClass):
    name = models.CharField(max_length=100, verbose_name="nome", help_text="Razão social ou nome fantasia. Exemplo: Distribuidora Boa Vista Ltda")
    session_name = models.CharField(
        max_length=30, blank=True, verbose_name="apelido para sessão",
        help_text="Nome curto exibido no cabeçalho da página para identificar a empresa da sessão atual. Se ficar em branco, será usado o nome da empresa.",
    )
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="descrição", help_text="Resumo opcional da empresa. Exemplo: Atacado de materiais de escritório")
    cnpj = models.CharField(max_length=18, verbose_name="CNPJ", help_text="Formato: 00.000.000/0000-00")
    manager = models.ManyToManyField('auth.User', related_name='%(app_label)s_%(class)s_manager', verbose_name="gerentes", help_text="Aprovam pedidos, cadastram produtos e veem os pedidos de toda a empresa. Superusuários sempre são gerentes.")
    sales_rep = models.ManyToManyField('auth.User', blank=True, related_name='%(app_label)s_%(class)s_sales_rep', verbose_name="representantes", help_text="Criam pedidos e veem apenas os pedidos que eles mesmos criaram.")

    def __str__(self):
        return "{} ({})".format(self.name, format_cnpj(self.cnpj))

    @property
    def display_name(self):
        # Nome mostrado no cabeçalho para a empresa da sessão
        return self.session_name or self.name

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['name']


class Client(BaseClass):
    name = models.CharField(max_length=100, verbose_name="nome", help_text="Nome ou razão social do cliente. Exemplo: Papelaria Central Ltda")
    cnpj_cpf = models.CharField(max_length=18, verbose_name="CNPJ/CPF", help_text="Formato: 00.000.000/0000-00 ou 000.000.000-00")
    # O endereço dele é opcional
    address = models.CharField(max_length=100, null=True, blank=True, verbose_name="endereço", help_text="Rua e número. Exemplo: Rua das Flores, 120")
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name="cidade", help_text="Exemplo: Curitiba")
    uf = models.CharField(max_length=2, verbose_name="UF", help_text="Sigla do estado, com 2 letras. Exemplo: PR")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='clients', verbose_name="empresa")

    def __str__(self):
        return "{} ({})".format(self.name, format_cpf_cnpj(self.cnpj_cpf))

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['name']


class MeasureUnit(models.TextChoices):
    UNIT = "UND", "[UND] Unidade"
    KIT = "KIT", "[KIT] Kit"
    CX6 = "CX6", "[CX6] Caixa com 6 peças"
    CX7 = "CX7", "[CX7] Caixa com 7 peças"
    CX8 = "CX8", "[CX8] Caixa com 8 peças"


class PaymentMethod(models.TextChoices):
    DINHEIRO = "dinheiro", "1 - Dinheiro"
    PIX = "pix", "2 - Pix"
    BOLETO = "boleto 30dias", "3 - Boleto(30)"
    BOLETO15 = "boleto 15dias", "4 - Boleto(15)"
    BOLETO7 = "boleto 7dias", "5 - Boleto(7)"
    CREDITO = "credito", "6 - Crédito"
    DEBITO = "debido", "7 - Débito"
    CREDIARIO =  "crediario", "8 - Crediário"


class Product(BaseClass):
    name = models.CharField(max_length=100, verbose_name="nome", help_text="Nome que aparece nos pedidos. Exemplo: Caderno universitário 96 folhas")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="descrição", help_text="Detalhes opcionais do produto. Exemplo: Capa dura, espiral, 10 matérias")
    sku = models.CharField(max_length=20, verbose_name="SKU", help_text="Código único do produto (Stock Keeping Unit). Exemplo: CAD-096-AZ")
    color = models.CharField(max_length=50, null=True, blank=True, verbose_name="cor", help_text="Opcional. Exemplo: Azul")
    measure_unit = models.CharField(max_length=5, choices=MeasureUnit.choices, default=MeasureUnit.UNIT, verbose_name="unidade de medida", help_text="Como o produto é vendido. Exemplo: Caixa com 6 peças")
    unit_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor unitário", help_text="Preço de uma unidade, em reais. Exemplo: 19.90")
    stock = models.PositiveIntegerField(default=0, verbose_name="estoque", help_text="Quantidade disponível. O pedido enviado baixa o estoque e o cancelado devolve. Exemplo: 150")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='products', verbose_name="empresa")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.sku, self.name, self.stock, self.unit_value)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['name']


class OrderStatus(models.TextChoices):
    EM_DIGITACAO = "digitacao", "Em digitação"
    PENDENTE = "pendente", "Pendente"
    APROVADO = "aprovado", "Aprovado"
    REJEITADO = "rejeitado", "Rejeitado"
    CANCELADO = "cancelado", "Cancelado"


class Order(BaseClass):
    TYPES=(
        ("IN", "Entrada"),
        ("OUT", "Saída"),
    )
    type = models.CharField(max_length=3, choices=TYPES, default="OUT", verbose_name="tipo", help_text="Saída é a venda para o cliente; entrada é uma devolução ou compra.")
    # Regras de mudança de status e de estoque: cadastros/pedidos.py
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.EM_DIGITACAO, verbose_name="status", help_text="Rascunho, aguardando aprovação do gerente, aprovado, rejeitado ou cancelado.")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='orders', verbose_name="empresa")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders', verbose_name="cliente", help_text="Cliente que está fazendo o pedido.")
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PIX, verbose_name="método de pagamento", help_text="Como o cliente vai pagar. Exemplo: Boleto(30)")
    total_value = models.DecimalField(default=0.00, max_digits=10, decimal_places=2, verbose_name="valor total", help_text="Soma dos itens já com os descontos; calculado pelo sistema.")
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="endereço", help_text="Endereço de entrega, se for diferente do cadastro. Exemplo: Av. Brasil, 500, sala 3")
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name="cidade", help_text="Cidade de entrega. Exemplo: Curitiba")
    uf = models.CharField(max_length=2, verbose_name="UF", help_text="Sigla do estado de entrega, com 2 letras. Exemplo: PR")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.id, self.client, self.created_by, self.total_value)
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-id']
    

class ProductOrder(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='product_orders', verbose_name="pedido")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name='product_orders', verbose_name="produto")
    quantity = models.PositiveIntegerField(verbose_name="quantidade", help_text="Unidades pedidas. Não pode passar do estoque ao enviar o pedido.")
    unit_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor unitário", help_text="Preço da unidade no momento do pedido, copiado do produto.")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="desconto", help_text="Desconto em reais sobre o total do item. Exemplo: 5.00")  # NOVO
    total_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor total", help_text="Quantidade x valor unitário - desconto; calculado pelo sistema.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="atualizado em")
    
    def __str__(self):
        return "{} | {} -> {} = {}".format(self.order.id, self.product.name, self.quantity, self.total_value)

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"
        ordering = ['id']