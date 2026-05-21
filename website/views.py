from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView


class IndexView(TemplateView):
    template_name = "website/model.html"


class UserLoginView(LoginView):
    template_name = "website/startbootstrap-sigep/login.html"
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    template_name = "website/startbootstrap-sigep/logout.html"

    def get_next_page(self):
        return None

class ContactView(TemplateView):
    template_name = "website/contact.html"

class AboutView(TemplateView):
    template_name = "website/startbootstrap-sigep/about.html"

# erros

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/401.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/404.html"

class CompanyChartsView(TemplateView):
    template_name = "website/startbootstrap-sigep/errors/500.html"