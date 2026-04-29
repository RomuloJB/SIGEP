from django.db import models

# Create your models here.

class Field(models.Model):
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, verbose_name="descrição")

    def __str__(self): # O metodo self é igual ao método this do java
        return "{} ({})".format(self.name, self.description) # define a forma como aparecerão os itens na tabela
    
class Company(models.Model):
    field = models.ForeignKey(Field, on_delete=models.PROTECT)
    cnpj = models.CharField(max_length=14)
    # manager = models.Manager(verbose_name= "gerente") ?????
    # sales_rep = models.Sales_Rep(verbose_name= "representante") ?????

    def __str__(self):
        return "{} ({})".format(self.field.name, self.cnpj)

class User_Profile(models.Model):
    field = models.ForeignKey(Field, on_delete=models.PROTECT)
    phone = models.CharField(max_length=11, verbose_name="Telefone")
    cpf = models.CharField(max_length=11)

    def __str__(self):
        return "{}".format(self.name)

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

class Order(models.Model):
    # type = models.??
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    # sales_rep = models.??()
    # client = models.??()
    field = models.ForeignKey(Field, on_delete=models.PROTECT)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PIX, verbose_name="Método de Pagamento")
    total_value = models.FloatField(verbose_name="Valor Total")
    address = models.CharField(max_length=255, verbose_name="Endereço")

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.id, self.client, self.sales_rep, self.value)

class Product(models.Model):
    field = models.ForeignKey(Field, on_delete=models.PROTECT)
    sku = models.CharField(max_length=20)
    color = models.CharField(max_length=50, verbose_name="Cor")
    unit_value = models.FloatField(verbose_name="Valor Unitario")
    stock = models.PositiveIntegerField(verbose_name="Estoque")
    measure_unit = models.CharField(max_length=5, choices=MeasureUnit.choices, default=MeasureUnit.UNIT, verbose_name="Unidade de Medida")
    company = models.ForeignKey(Company, on_delete=models.PROTECT)

    def __str__(self):
        return "{} | {} -> {} = {}".format(self.sku, self.field.name, self.stock, self.unit_value)

# class Recharge(models.Model):
    

# class License(models.Model):


