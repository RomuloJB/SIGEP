from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name = 'usuarios/login.html'
        # extra_context titulo e botao
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name = 'usuarios/password_change.html'
    ), name="password-change"),
]