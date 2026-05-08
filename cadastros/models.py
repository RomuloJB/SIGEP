from django.db import models

# Create your models here.

class User_Profile(models.Model):
    name = models.CharField(max_length=255, verbose_name="nome")
    phone = models.CharField(max_length=11, verbose_name="telefone")
    cpf = models.CharField(max_length=14, verbose_name="CPF")

    def __str__(self):
        return "{}".format(self.name)


class BaseClass(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="atualizado em")
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='%(app_label)s_%(class)s_created_by', verbose_name="criado por")
    
    class Meta: abstract = True


class Company(BaseClass):
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, verbose_name="descrição")
    cnpj = models.CharField(max_length=14)
    manager = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='%(app_label)s_%(class)s_manager', verbose_name="Gerente")
    sales_rep = models.ManyToManyField('auth.User', verbose_name="representantes")

    def __str__(self):
        return "{} ({})".format(self.name, self.cnpj)


class Client(BaseClass):
    name = models.CharField(max_length=255, verbose_name="nome")
    cnpj_cpf = models.CharField(max_length=14, verbose_name="CNPJ/CPF")
    uf = models.CharField(max_length=2, verbose_name="UF")

    def __str__(self):
        return "{} ({})".format(self.name, self.cnpj_cpf)


class MeasureUnit(models.TextChoices):
    UNIT = "UND", "Unidade"
    KIT = "KIT", "Kit"
    CX6 = "CX6", "Caixa com 6 peças"
    CX7 = "CX7", "Caixa com 7 peças"
    CX8 = "CX8", "Caixa com 8 peças"


class PaymentMethod(models.TextChoices):
    DINHEIRO = "1", "Dinheiro"
    PIX = "2", "Pix"
    BOLETO = "3", "Boleto(30)"
    BOLETO15 = "4", "Boleto(15)"
    BOLETO7 = "5", "Boleto(7)"
    CREDITO = "6", "Crédito"
    DEBITO = "7", "Débito"
    CREDIARIO =  "8", "Crediário"


class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, verbose_name="descrição")
    sku = models.CharField(max_length=20, verbose_name="SKU")
    color = models.CharField(max_length=50, verbose_name="cor")
    unit_value = models.FloatField(verbose_name="valor unitário")
    stock = models.PositiveIntegerField(verbose_name="estoque")
    measure_unit = models.CharField(max_length=5, choices=MeasureUnit.choices, default=MeasureUnit.UNIT, verbose_name="unidade de medida")
    company = models.ForeignKey(Company, on_delete=models.PROTECT)

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.sku, self.field.name, self.stock, self.unit_value)


class Order(BaseClass):
    TYPES=(
        ("IN", "Entrada"),
        ("OUT", "Saída"),
    )
    type = models.CharField(max_length=3, choices=TYPES, default="IN", verbose_name="tipo")
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PIX, verbose_name="método de pagamento")
    total_value = models.FloatField(verbose_name="valor total")
    address = models.CharField(max_length=255, verbose_name="endereço")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.id, self.client, self.created_by, self.total_value)
    

class ProductOrder(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(verbose_name="quantidade")
    unit_value = models.FloatField(verbose_name="valor unitário")
    total_value = models.FloatField(verbose_name="valor total")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.order.id, self.product.name, self.quantity, self.total_value)