from django.urls import path

from .views import (
    IndexView,
    # Company
    CompanyCreate, CompanyUpdate, CompanyDelete, CompanyList, CompanyDetail,
    # Client
    ClientCreate, ClientUpdate, ClientDelete, ClientList, ClientDetail,
    ProductDataView,
    # User Profile
    UserProfileCreate, UserProfileUpdate, UserProfileDelete, UserProfileList, UserProfileDetail,
    # Order
    OrderCreate, OrderUpdate, OrderDelete, OrderList, OrderDetail,
    # Product
    ProductCreate, ProductUpdate, ProductDelete, ProductList, ProductDetail,
)

urlpatterns = [
    path("", IndexView.as_view(), name="index"),

    # Company (Empresa)
    path("company/create/", CompanyCreate.as_view(), name="company-create"),
    path("company/<int:pk>/update/", CompanyUpdate.as_view(), name="company-update"),
    path("company/<int:pk>/delete/", CompanyDelete.as_view(), name="company-delete"),
    path("company/", CompanyList.as_view(), name="company-list"),
    path("company/<int:pk>/", CompanyDetail.as_view(), name="company-detail"),

    # Client (Cliente)
    path("client/create/", ClientCreate.as_view(), name="client-create"),
    path("client/<int:pk>/update/", ClientUpdate.as_view(), name="client-update"),
    path("client/<int:pk>/delete/", ClientDelete.as_view(), name="client-delete"),
    path("client/", ClientList.as_view(), name="client-list"),
    path("client/<int:pk>/", ClientDetail.as_view(), name="client-detail"),

    # User_Profile (Perfil de Usuário)
    path("userprofile/create/", UserProfileCreate.as_view(), name="userprofile-create"),
    path("userprofile/<int:pk>/update/", UserProfileUpdate.as_view(), name="userprofile-update"),
    path("userprofile/<int:pk>/delete/", UserProfileDelete.as_view(), name="userprofile-delete"),
    path("userprofile/", UserProfileList.as_view(), name="userprofile-list"),
    path("userprofile/<int:pk>/", UserProfileDetail.as_view(), name="userprofile-detail"),

    # Order (Pedido)
    path("order/create/", OrderCreate.as_view(), name="order-create"),
    path("order/<int:pk>/update/", OrderUpdate.as_view(), name="order-update"),
    path("order/<int:pk>/delete/", OrderDelete.as_view(), name="order-delete"),
    path("order/", OrderList.as_view(), name="order-list"),
    path("order/<int:pk>/", OrderDetail.as_view(), name="order-detail"),

    # Product (Produto)
    path("product/create/", ProductCreate.as_view(), name="product-create"),
    path("product/<int:pk>/update/", ProductUpdate.as_view(), name="product-update"),
    path("product/<int:pk>/delete/", ProductDelete.as_view(), name="product-delete"),
    path("product/", ProductList.as_view(), name="product-list"),
    path("product/<int:pk>/", ProductDetail.as_view(), name="product-detail"),

    # API auxiliar – dados de produto (usada pelo JS do formulário de pedido)
    path("api/product/<int:pk>/", ProductDataView.as_view(), name="product-data"),
]