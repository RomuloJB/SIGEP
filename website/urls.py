from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CompanyDetailView, CompanyListView, IndexView, ContactView, AboutView, CompanyView,
    ManagerView, ManagerListView, ManagerDetailView, VendorView, VendorListView, VendorDetailView, ClientView, ClientListView, ClientDetailView, ProductView, ProductListView, ProductDetailView, PedidoView, PedidoListView, PedidoDetailView, CompanyChartsView, CompanyListView
)

urlpatterns = [
    # path('url/navegador', Class.as_view(), name='nome_do_link'),
    path("", IndexView.as_view(), name="index"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("about/", AboutView.as_view(), name="about"),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="website/startbootstrap-sigep/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    #Paginas sidenav
    path("company-chart/", CompanyChartsView.as_view(), name="company-chart"),
    path("company-list/", CompanyListView.as_view(), name="company-list"),
]
