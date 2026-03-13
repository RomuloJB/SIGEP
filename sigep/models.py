from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Historico(models.Model):
    nome = models.CharField(max_length=255)
    atualizado_em = models.DateTimeField(auto_now=True)
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.CharField(User, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome}"
    
class Gerente(models.Model):
    id_gerente = models.AutoField(max_length=255, verbose_name="ID do Gerente")
    nome = models.CharField(max_length=255)
    atualizado_em = models.DateTimeField(auto_now=True)
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.CharField(User, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome}"
    
class Representante(models.Model):
    nome = models.CharField(max_length=255)
    atualizado_em = models.DateTimeField(auto_now=True)
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.CharField(User, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome}"
    
class Cliente(models.Model):
    nome = models.CharField(max_length=255)
    atualizado_em = models.DateTimeField(auto_now=True)
    cadastrado_em = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.CharField(User, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.nome}"