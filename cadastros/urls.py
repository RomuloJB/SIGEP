from django.urls import path
#from .views import ()

from .views import (
    FieldCreate, FieldUpdate, FieldDelete, FieldList, FieldDetail,
    CompanyCreate, CompanyUpdate, CompanyDelete, CompanyList, CompanyDetail,
    UserProfileCreate, UserProfileUpdate, UserProfileDelete, UserProfileList, UserProfileDetail,
    OrderCreate, OrderUpdate, OrderDelete, OrderList, OrderDetail,
    ProductCreate, ProductUpdate, ProductDelete, ProductList, ProductDetail,
)

urlpatterns = [

    # Field (Ramo)
    path('cadastrar/field/', FieldCreate.as_view(), name='field-create'),
    path('atualizar/field/<int:pk>/', FieldUpdate.as_view(), name='field-update'),
    path('excluir/field/<int:pk>/', FieldDelete.as_view(), name='field-delete'),
    path('listar/field/', FieldList.as_view(), name='field-list'),
    path('detalhar/field/<int:pk>/', FieldDetail.as_view(), name='field-detail'),

    # Company (Empresa)
    path('cadastrar/company/', CompanyCreate.as_view(), name='company-create'),
    path('atualizar/company/<int:pk>/', CompanyUpdate.as_view(), name='company-update'),
    path('excluir/company/<int:pk>/', CompanyDelete.as_view(), name='company-delete'),
    path('listar/company/', CompanyList.as_view(), name='company-list'),
    path('detalhar/company/<int:pk>/', CompanyDetail.as_view(), name='company-detail'),

    # User_Profile (Perfil de Usuário)
    path('cadastrar/userprofile/', UserProfileCreate.as_view(), name='userprofile-create'),
    path('atualizar/userprofile/<int:pk>/', UserProfileUpdate.as_view(), name='userprofile-update'),
    path('excluir/userprofile/<int:pk>/', UserProfileDelete.as_view(), name='userprofile-delete'),
    path('listar/userprofile/', UserProfileList.as_view(), name='userprofile-list'),
    path('detalhar/userprofile/<int:pk>/', UserProfileDetail.as_view(), name='userprofile-detail'),

    # Order (Pedido)
    path('cadastrar/order/', OrderCreate.as_view(), name='order-create'),
    path('atualizar/order/<int:pk>/', OrderUpdate.as_view(), name='order-update'),
    path('excluir/order/<int:pk>/', OrderDelete.as_view(), name='order-delete'),
    path('listar/order/', OrderList.as_view(), name='order-list'),
    path('detalhar/order/<int:pk>/', OrderDetail.as_view(), name='order-detail'),

    # Product (Produto)
    path('cadastrar/product/', ProductCreate.as_view(), name='product-create'),
    path('atualizar/product/<int:pk>/', ProductUpdate.as_view(), name='product-update'),
    path('excluir/product/<int:pk>/', ProductDelete.as_view(), name='product-delete'),
    path('listar/product/', ProductList.as_view(), name='product-list'),
    path('detalhar/product/<int:pk>/', ProductDetail.as_view(), name='product-detail'),

]