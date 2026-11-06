// Sidebar (website/sidebar.html). Computador: recolhe para só ícones e lembra a escolha
// neste navegador. Celular/tablet: gaveta por cima da página, aberta pelo botão da barra
// superior. A classe sidebar-recolhida é aplicada antes pelo <head> do model.html, para
// a página não piscar expandida.
(function () {
    var raiz = document.documentElement;
    var sidebar = document.getElementById('appSidebar');
    if (!sidebar) return;

    var CHAVE = 'sigep|sidebar-recolhida';
    var celular = window.matchMedia('(max-width: 991.98px)');
    var topo = document.querySelector('.sb-topnav');
    var conteudo = document.getElementById('appContent');
    var fundo = document.getElementById('sidebarFundo');
    var botaoTopo = document.getElementById('sidebarToggle');
    var botaoRecolher = document.getElementById('sidebarRecolher');
    var botaoFechar = document.getElementById('sidebarFechar');

    function recolhida() {
        return raiz.classList.contains('sidebar-recolhida');
    }

    function atualizarRecolhida() {
        var mostrarDicas = recolhida() && !celular.matches;
        var acao = recolhida() ? 'Expandir menu' : 'Recolher menu';
        botaoRecolher.setAttribute('aria-expanded', String(!recolhida()));
        botaoRecolher.setAttribute('aria-label', acao);
        botaoRecolher.title = acao;
        // Sem texto na tela, o nome de cada opção aparece como dica ao parar o mouse
        sidebar.querySelectorAll('[data-rotulo]').forEach(function (link) {
            if (mostrarDicas) {
                link.title = link.dataset.rotulo;
            } else {
                link.removeAttribute('title');
            }
        });
    }

    function alternarRecolhida() {
        raiz.classList.toggle('sidebar-recolhida');
        try {
            localStorage.setItem(CHAVE, recolhida() ? '1' : '0');
        } catch (e) {
            // Sem acesso ao armazenamento: vale só até recarregar a página
        }
        atualizarRecolhida();
    }

    function gavetaAberta() {
        return raiz.classList.contains('sidebar-aberta');
    }

    function abrirGaveta() {
        raiz.classList.add('sidebar-aberta');
        botaoTopo.setAttribute('aria-expanded', 'true');
        // O resto da página sai do alcance do teclado enquanto a gaveta está aberta
        topo.inert = true;
        conteudo.inert = true;
        botaoFechar.focus();
    }

    function fecharGaveta(devolverFoco) {
        if (!gavetaAberta()) return;
        raiz.classList.remove('sidebar-aberta');
        botaoTopo.setAttribute('aria-expanded', 'false');
        topo.inert = false;
        conteudo.inert = false;
        if (devolverFoco) botaoTopo.focus();
    }

    botaoTopo.addEventListener('click', abrirGaveta);
    botaoRecolher.addEventListener('click', alternarRecolhida);
    botaoFechar.addEventListener('click', function () { fecharGaveta(true); });
    fundo.addEventListener('click', function () { fecharGaveta(true); });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') fecharGaveta(true);
    });

    // Ao escolher uma opção a página muda; a gaveta não fica aberta ao voltar
    sidebar.addEventListener('click', function (e) {
        if (e.target.closest('a')) fecharGaveta(false);
    });

    // Girar o tablet ou aumentar a janela sai do modo gaveta
    celular.addEventListener('change', function () {
        fecharGaveta(false);
        atualizarRecolhida();
    });

    atualizarRecolhida();
})();
