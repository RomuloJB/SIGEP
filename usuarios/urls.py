from django.urls import path
from django.contrib.auth import views as auth_views
from .views import SelectCompanyView, ActivateCompanyView, UserListView, UserUpdateView, UserRegisterView

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name = 'usuarios/login.html'
        # extra_context titulo e botao
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name = 'usuarios/password_change.html'
    ), name="password-change"),
    path("select-company/", SelectCompanyView.as_view(), name="select-company"),
    path("activate-company/<int:pk>/", ActivateCompanyView.as_view(), name="activate-company"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/update/", UserUpdateView.as_view(), name="user-update"),
    path("register/", UserRegisterView.as_view(), name="register"),
]