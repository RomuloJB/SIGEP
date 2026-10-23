from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .views import (
    SelectCompanyView, ActivateCompanyView, UserListView, UserCreateView, UserUpdateView,
    UserRegisterView, MyProfileView, MyPasswordChangeView,
)

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(
        template_name = 'usuarios/login.html'
        # extra_context titulo e botao
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("my-profile/", MyProfileView.as_view(), name="my-profile"),
    path("password-change/", MyPasswordChangeView.as_view(), name="password-change"),

    # Redefinição de senha por e-mail (fluxo nativo do Django: token de uso único que expira)
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name = 'usuarios/forgot_password.html',
        email_template_name = 'usuarios/emails/password_reset_email.txt',
        html_email_template_name = 'usuarios/emails/password_reset_email.html',
        subject_template_name = 'usuarios/emails/password_reset_subject.txt',
        success_url = reverse_lazy('password-reset-done'),
    ), name="password-reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name = 'usuarios/password_reset_done.html'
    ), name="password-reset-done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name = 'usuarios/password_reset_confirm.html',
        success_url = reverse_lazy('password-reset-complete'),
    ), name="password-reset-confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name = 'usuarios/password_reset_complete.html'
    ), name="password-reset-complete"),

    path("select-company/", SelectCompanyView.as_view(), name="select-company"),
    path("activate-company/<int:pk>/", ActivateCompanyView.as_view(), name="activate-company"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/create/", UserCreateView.as_view(), name="user-create"),
    path("users/<int:pk>/update/", UserUpdateView.as_view(), name="user-update"),
    path("register/", UserRegisterView.as_view(), name="register"),
]