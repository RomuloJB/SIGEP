"""
Testes de carga do SIGEP com o Locust (CC01 em diante).

Cada usuário virtual é um representante da Empresa A: entra no sistema, ativa a
empresa e repete o fluxo dashboard -> lista de pedidos -> lista de produtos ->
/api/product/<id>/, com 1 a 3 s entre as ações. Cada caso de teste tem um .conf
nesta pasta com usuários, taxa de entrada, duração e critérios de aceitação.

Rode SEMPRE contra a homologação (App Engine apontando para um branch do Neon só
de testes), nunca contra a produção:

    pip install -r testes/carga/requirements.txt
    $env:CARGA_SENHA = "<senha dos representantes de teste>"
    locust -f testes/carga/locustfile.py --config testes/carga/cc01.conf --host https://<homologacao>

Variáveis de ambiente:
    CARGA_SENHA            senha dos representantes de teste (obrigatória).
    CARGA_USUARIO_PREFIXO  prefixo dos logins: o usuário virtual n entra como
                           <prefixo><n com 2 dígitos>. Padrão "carga" (carga01, carga02...).
    CARGA_EMPRESA_ID       id da Empresa A. Só é preciso se os representantes
                           tiverem mais de uma empresa (com uma só ela é ativada direto).

No fim, o Locust sai com código 1 se alguma rota passar do p95 máximo ou se a
taxa de falhas passar do limite (--p95-maximo-ms e --falhas-maximo no .conf).
"""
import itertools
import logging
import os
import random
import re

from locust import HttpUser, SequentialTaskSet, between, events, task
from locust.exception import StopUser

CSRF = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
LINK_DE_PRODUTO = re.compile(r'href="/product/(\d+)/"')

# Cada usuário virtual pega o próximo número: carga01, carga02, ...
_proximo_numero = itertools.count(1)


@events.init_command_line_parser.add_listener
def _criterios_na_linha_de_comando(parser):
    parser.add_argument("--p95-maximo-ms", type=float, default=3000,
                        help="p95 máximo aceito em cada rota, em milissegundos")
    parser.add_argument("--falhas-maximo", type=float, default=0.01,
                        help="taxa de falhas máxima aceita (0.01 = 1%%)")


@events.quitting.add_listener
def _conferir_criterios_de_aceitacao(environment, **kwargs):
    opcoes = environment.parsed_options
    total = environment.stats.total
    problemas = []

    if total.num_requests == 0:
        problemas.append("nenhuma requisição foi feita")
    if total.fail_ratio > opcoes.falhas_maximo:
        problemas.append("taxa de falhas {:.2%} acima de {:.2%}".format(total.fail_ratio, opcoes.falhas_maximo))
    for rota in environment.stats.entries.values():
        p95 = rota.get_response_time_percentile(0.95)
        if p95 > opcoes.p95_maximo_ms:
            problemas.append("p95 de {} {} = {:.0f} ms (máximo {:.0f} ms)".format(
                rota.method, rota.name, p95, opcoes.p95_maximo_ms))

    if problemas:
        logging.error("Critérios de aceitação NÃO atendidos:\n  - %s", "\n  - ".join(problemas))
        environment.process_exit_code = 1
    else:
        logging.info("Critérios de aceitação atendidos: p95 <= %.0f ms em todas as rotas e falhas <= %.2f%%.",
                     opcoes.p95_maximo_ms, opcoes.falhas_maximo * 100)


class FluxoDoRepresentante(SequentialTaskSet):
    """Uma volta do fluxo; ao terminar, o Locust recomeça do dashboard."""

    @task
    def dashboard(self):
        self.user.abrir("/", "dashboard")

    @task
    def lista_de_pedidos(self):
        self.user.abrir("/order/", "lista de pedidos")

    @task
    def lista_de_produtos(self):
        resposta = self.user.abrir("/product/", "lista de produtos")
        if resposta is not None:
            self.user.produtos = LINK_DE_PRODUTO.findall(resposta.text) or self.user.produtos

    @task
    def dados_do_produto(self):
        url = "/api/product/{}/".format(self.user.produto_qualquer())
        with self.client.get(url, name="/api/product/[id]/", catch_response=True) as resposta:
            if resposta.status_code != 200:
                resposta.failure("status {}".format(resposta.status_code))
            elif "id" not in resposta.json():
                resposta.failure("JSON sem o produto")


class Representante(HttpUser):
    wait_time = between(1, 3)
    tasks = [FluxoDoRepresentante]

    def on_start(self):
        self.produtos = []
        senha = os.environ.get("CARGA_SENHA")
        if not senha:
            logging.error("Defina a variável de ambiente CARGA_SENHA com a senha dos representantes de teste.")
            self.environment.runner.quit()
            raise StopUser()

        prefixo = os.environ.get("CARGA_USUARIO_PREFIXO", "carga")
        self.usuario = "{}{:02d}".format(prefixo, next(_proximo_numero))
        if not (self.entrar(senha) and self.ativar_empresa()):
            raise StopUser()

    # ─── Entrada no sistema ──────────────────────────────────────────────────

    def entrar(self, senha):
        tela = self.client.get("/login/", name="/login/")
        token = CSRF.search(tela.text)
        if not token:
            logging.error("Tela de login sem token CSRF (status %s).", tela.status_code)
            return False

        # Sem seguir o redirecionamento: o tempo do login não soma o do dashboard.
        # O Referer é exigido pelo CSRF do Django em HTTPS.
        with self.client.post(
            "/login/",
            data={"username": self.usuario, "password": senha, "csrfmiddlewaretoken": token.group(1)},
            headers={"Referer": self.host.rstrip("/") + "/login/"},
            name="/login/ (enviar)", allow_redirects=False, catch_response=True,
        ) as resposta:
            if resposta.status_code != 302:
                resposta.failure("login recusado para {} (status {})".format(self.usuario, resposta.status_code))
                return False
        return True

    def ativar_empresa(self):
        empresa = os.environ.get("CARGA_EMPRESA_ID")
        url, nome = ("/activate-company/{}/".format(empresa), "/activate-company/[id]/") if empresa \
            else ("/select-company/", "/select-company/")

        with self.client.get(url, name=nome, allow_redirects=False, catch_response=True) as resposta:
            # Com uma empresa só (ou com CARGA_EMPRESA_ID) a empresa é ativada e o
            # usuário vai para o dashboard; 200 seria a tela de escolha
            if resposta.status_code != 302:
                resposta.failure("{} não ativou a empresa (status {}): defina CARGA_EMPRESA_ID".format(
                    self.usuario, resposta.status_code))
                return False
        return True

    # ─── Navegação ───────────────────────────────────────────────────────────

    def abrir(self, url, descricao):
        with self.client.get(url, name=url, catch_response=True) as resposta:
            if resposta.status_code != 200:
                resposta.failure("{}: status {}".format(descricao, resposta.status_code))
                return None
            # Sessão perdida ou empresa desativada viram redirecionamento para estas telas
            if "/login/" in resposta.url or "/select-company/" in resposta.url:
                resposta.failure("{}: caiu em {}".format(descricao, resposta.url))
                return None
            return resposta

    def produto_qualquer(self):
        if not self.produtos:
            resposta = self.abrir("/product/", "lista de produtos")
            if resposta is not None:
                self.produtos = LINK_DE_PRODUTO.findall(resposta.text)
        return random.choice(self.produtos) if self.produtos else "0"
