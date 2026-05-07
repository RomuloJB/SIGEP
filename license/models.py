from django.db import models
from cadastros.models import Company

# Create your models here.

class CompanyLicense(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    expiration_date = models.DateField(verbose_name="data de expiração")

    def __str__(self):
        return "{} - {}".format(self.company.name, self.license_key)
    
    
class Plan(models.Model):
    name = models.CharField(max_length=255, verbose_name="nome")
    description = models.CharField(max_length=255, verbose_name="descrição")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="preço")
    days = models.IntegerField(verbose_name="dias de validade")

    def __str__(self):
        return self.name
    

class Recharge(models.Model):
    company_license = models.ForeignKey(CompanyLicense, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    recharge_date = models.DateField(verbose_name="data de recarga")
    payed_at = models.DateField(verbose_name="data de pagamento")

    def __str__(self):
        return "{} - {}".format(self.company_license.company.name, self.plan.name)