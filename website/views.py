from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "website/model.html"

class ContactView(TemplateView):
    template_name = "website/contact.html"