from django.urls import path
from .views import (
    IndexView, ContactView, AboutView, CompanyChartsView
)

urlpatterns = [
    # path('url/navegador', Class.as_view(), name='nome_do_link'),
    path("", IndexView.as_view(), name="index"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("about/", AboutView.as_view(), name="about"),

    #Paginas sidenav
    path("company-chart/", CompanyChartsView.as_view(), name="company-chart"),
]
