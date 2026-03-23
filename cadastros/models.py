from django.db import models

# Create your models here.

class Campo(models.Model):
    nome = models.CharField(max_length=255)
    descricao = models.CharField(max_length=255, verbose_name="descrição")
