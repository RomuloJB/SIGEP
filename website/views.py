from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "website/model.html"

class ContactView(TemplateView):
    template_name = "website/contact.html"

class AboutView(TemplateView):
    template_name = "website/about.html"

# empresas
class CompanyView(TemplateView):
    template_name = "website/company.html"

class CompanyListView(TemplateView):
    template_name = "website/company_list.html"

class CompanyDetailView(TemplateView):
    template_name = "website/company_detail.html"

# gerentes
class ManagerView(TemplateView):
    template_name = "website/manager.html"

class ManagerListView(TemplateView):
    template_name = "website/manager_list.html"

class ManagerDetailView(TemplateView):
    template_name = "website/manager_detail.html"


# representantes
class VendorView(TemplateView):
    template_name = "website/vendor.html"

class VendorListView(TemplateView):
    template_name = "website/vendor_list.html"

class VendorDetailView(TemplateView):
    template_name = "website/vendor_detail.html"


# clientes
class ClientView(TemplateView):
    template_name = "website/client.html"

class ClientListView(TemplateView):
    template_name = "website/client_list.html"

class ClientDetailView(TemplateView):
    template_name = "website/client_detail.html"


# produtos
class ProductView(TemplateView):
    template_name = "website/product.html"

class ProductListView(TemplateView):
    template_name = "website/product_list.html"

class ProductDetailView(TemplateView):
    template_name = "website/product_detail.html"


# pedidos
class PedidoView(TemplateView):
    template_name = "website/pedido.html"

class PedidoListView(TemplateView):
    template_name = "website/pedido_list.html"

class PedidoDetailView(TemplateView):
    template_name = "website/pedido_detail.html"

# 