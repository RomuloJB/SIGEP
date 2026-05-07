from django.contrib import admin
from .models import Client, Company, Order, Product, User_Profile

# Register your models here.
admin.site.register(User_Profile)
admin.site.register(Company)
admin.site.register(Product)
admin.site.register(Client)
admin.site.register(Order)