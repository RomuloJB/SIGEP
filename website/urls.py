from django.urls import path
from .views import (
    CompanyDetailView, CompanyListView, IndexView, ContactView, AboutView, CompanyView,
    ManagerView, ManagerListView, ManagerDetailView,
    VendorView, VendorListView, VendorDetailView,
    ClientView, ClientListView, ClientDetailView,
    ProductView, ProductListView, ProductDetailView,
    PedidoView, PedidoListView, PedidoDetailView
)

urlpatterns = [
    # path('url/navegador', Class.as_view(), name='nome_do_link'),
    path("", IndexView.as_view(), name="index"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("sobre/", AboutView.as_view(), name="about"),

    # Empresas
    path("company/", CompanyView.as_view(), name="company"),
    path("company/list/", CompanyListView.as_view(), name="company_list"),
    path("company/detail/", CompanyDetailView.as_view(), name="company_detail"),

    
    # Gerentes
    path("manager/", ManagerView.as_view(), name="manager"),
    path("manager/list/", ManagerListView.as_view(), name="manager_list"),
    path("manager/detail/", ManagerDetailView.as_view(), name="manager_detail"),
    
    # Representantes
    path("vendor/", VendorView.as_view(), name="vendor"),
    path("vendor/list/", VendorListView.as_view(), name="vendor_list"),
    path("vendor/detail/", VendorDetailView.as_view(), name="vendor_detail"),
    
    # Clientes
    path("client/", ClientView.as_view(), name="client"),
    path("client/list/", ClientListView.as_view(), name="client_list"),
    path("client/detail/", ClientDetailView.as_view(), name="client_detail"),
    
    # Produtos
    path("product/", ProductView.as_view(), name="product"),
    path("product/list/", ProductListView.as_view(), name="product_list"),
    path("product/detail/", ProductDetailView.as_view(), name="product_detail"),
    
    # Pedidos
    path("pedido/", PedidoView.as_view(), name="pedido"),
    path("pedido/list/", PedidoListView.as_view(), name="pedido_list"),
    path("pedido/detail/", PedidoDetailView.as_view(), name="pedido_detail"),

]
