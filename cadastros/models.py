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
    name = models.CharField(max_length=255, verbose_name="nome")
    phone = models.CharField(max_length=11, verbose_name="telefone")
    cpf = models.CharField(max_length=11)

    def __str__(self):
        return "{}".format(self.name)

class Order(models.Model):
    # type = models. sei la
    # company = models.Company()
    # sales_rep = models.Sales_Rep()
    # client = models.Client()
    payment_method = models.Payment()


class Recharge(models.Model):

class License(models.Model):

    def __str__(self):
        return "{} ({})".format(self.name, self.field.name)
