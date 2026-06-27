from django.db import models

# Create your models here.

class User_Profile(models.Model):
    name = models.CharField(max_length=255, verbose_name="nome")
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
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="descrição")
    cnpj = models.CharField(max_length=18, verbose_name="CNPJ", help_text="Formato: 00.000.000/0000-00")
    manager = models.ManyToManyField('auth.User', related_name='%(app_label)s_%(class)s_manager', verbose_name="gerentes")
    sales_rep = models.ManyToManyField('auth.User', blank=True, related_name='%(app_label)s_%(class)s_sales_rep', verbose_name="representantes")

    def __str__(self):
        return "{} ({})".format(self.name, self.cnpj)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['name']


class Client(BaseClass):
    name = models.CharField(max_length=255, verbose_name="nome")
    cnpj_cpf = models.CharField(max_length=18, verbose_name="CNPJ/CPF", help_text="Formato: 00.000.000/0000-00 ou 000.000.000-00")
    # O endereço dele é opcional
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="endereço")
    city = models.CharField(max_length=255, null=True, blank=True, verbose_name="cidade")
    uf = models.CharField(max_length=2, verbose_name="UF")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='clients', verbose_name="empresa")

    def __str__(self):
        return "{} ({})".format(self.name, self.cnpj_cpf)

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
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name="descrição")
    sku = models.CharField(max_length=20, verbose_name="SKU", help_text="Código único do produto (Stock Keeping Unit)")
    color = models.CharField(max_length=50, null=True, blank=True, verbose_name="cor")
    measure_unit = models.CharField(max_length=5, choices=MeasureUnit.choices, default=MeasureUnit.UNIT, verbose_name="unidade de medida")
    unit_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor unitário")
    stock = models.PositiveIntegerField(default=0, verbose_name="estoque")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='products', verbose_name="empresa")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.sku, self.name, self.stock, self.unit_value)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['name']


class Order(BaseClass):
    TYPES=(
        ("IN", "Entrada"),
        ("OUT", "Saída"),
    )
    type = models.CharField(max_length=3, choices=TYPES, default="IN", verbose_name="tipo")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='orders', verbose_name="empresa")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders', verbose_name="cliente")
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PIX, verbose_name="método de pagamento")
    total_value = models.DecimalField(default=0.00, max_digits=10, decimal_places=2, verbose_name="valor total")
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="endereço")
    city = models.CharField(max_length=255, null=True, blank=True, verbose_name="cidade")
    uf = models.CharField(max_length=2, verbose_name="UF")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.id, self.client, self.created_by, self.total_value)
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-id']
    

class ProductOrder(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='product_orders', verbose_name="pedido")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name='product_orders', verbose_name="produto")
    quantity = models.PositiveIntegerField(verbose_name="quantidade")
    unit_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor unitário")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="valor total")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="atualizado em")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.order.id, self.product.name, self.quantity, self.total_value)

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"
        ordering = ['id']