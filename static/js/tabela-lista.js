// Busca rápida e ordenação das tabelas de listagem (<table class="table-lista">),
// em JS puro. Só atua nas linhas que já estão na página (a paginação é do Django).
//
// - Busca: um campo no card-header, à direita, esconde as linhas sem a ocorrência
//   (ignora maiúsculas e acentos). Colunas com data-searchable="false" não entram.
// - Ordenação: cada <th> vira um botão: 1º clique crescente, 2º decrescente,
//   3º volta à ordem original. Colunas com data-orderable="false" ficam sem botão.
// - Valores: usa data-sort da célula quando existe; senão lê o texto no formato
//   brasileiro (R$ 1.250,00, 1.024, 31/12/2026 14:30, 11/2026, #12).
(function () {
    'use strict';

    const COLLATOR = new Intl.Collator('pt-BR', { numeric: true, sensitivity: 'base' });

    function normalizar(texto) {
        return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    // Converte o texto de uma célula em { tipo, valor } comparável.
    function interpretar(celula) {
        const bruto = celula.hasAttribute('data-sort')
            ? celula.getAttribute('data-sort').trim()
            : celula.textContent.trim();
        if (bruto === '' || bruto === '—' || bruto === '-') return { tipo: 'vazio' };

        // data-sort é padrão internacional (1234.50) ou ISO (2026-11-05 14:30)
        if (celula.hasAttribute('data-sort')) {
            if (/^-?\d+(\.\d+)?$/.test(bruto)) return { tipo: 'num', valor: parseFloat(bruto) };
            const iso = Date.parse(bruto.replace(' ', 'T'));
            if (/^\d{4}-\d{2}/.test(bruto) && !isNaN(iso)) return { tipo: 'num', valor: iso };
            return { tipo: 'texto', valor: bruto };
        }

        // Datas do Brasil: dd/mm/aaaa [hh:mm[:ss]] e mm/aaaa
        let m = bruto.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
        if (m) {
            return { tipo: 'num', valor: Date.UTC(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)) };
        }
        m = bruto.match(/^(\d{2})\/(\d{4})$/);
        if (m) return { tipo: 'num', valor: Date.UTC(+m[2], +m[1] - 1, 1) };

        // Números do Brasil: milhar com ponto, decimal com vírgula; aceita R$, US$, #, % e sinal
        const limpo = bruto.replace(/^(R\$|US\$|#)\s*/, '').replace(/\s*%$/, '');
        if (/^-?\d{1,3}(\.\d{3})*(,\d+)?$/.test(limpo) || /^-?\d+(,\d+)?$/.test(limpo)) {
            return { tipo: 'num', valor: parseFloat(limpo.replace(/\./g, '').replace(',', '.')) };
        }
        return { tipo: 'texto', valor: bruto };
    }

    function comparar(a, b) {
        // Vazios sempre no fim, números antes de textos
        if (a.tipo === 'vazio' || b.tipo === 'vazio') {
            return (a.tipo === 'vazio') - (b.tipo === 'vazio');
        }
        if (a.tipo === 'num' && b.tipo === 'num') return a.valor - b.valor;
        if (a.tipo !== b.tipo) return a.tipo === 'num' ? -1 : 1;
        return COLLATOR.compare(a.valor, b.valor);
    }

    const ICONE_ORDEM =
        '<span class="sort-icon" aria-hidden="true">' +
        '<svg viewBox="0 0 10 16" width="10" height="16"><path class="sort-up" d="M5 1 9 6H1z"/><path class="sort-down" d="M5 15 1 10h8z"/></svg>' +
        '</span>';

    function criarCampoBusca(card) {
        let ferramentas = card.querySelector('.card-header .card-tools');
        if (!ferramentas) {
            const cabecalho = card.querySelector('.card-header');
            if (!cabecalho) return null;
            ferramentas = document.createElement('div');
            ferramentas.className = 'card-tools';
            cabecalho.appendChild(ferramentas);
        }
        const rotulo = document.createElement('label');
        rotulo.className = 'tabela-busca';
        rotulo.innerHTML =
            '<span class="visually-hidden">Buscar nesta página</span>' +
            '<svg class="tabela-busca-icone" viewBox="0 0 512 512" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M416 208c0 45.9-14.9 88.3-40 122.7l126.6 126.7a32 32 0 0 1-45.2 45.2L330.7 376A208 208 0 1 1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 0 0 0 288z"/></svg>' +
            '<input type="search" class="form-control" placeholder="Buscar nesta página…" autocomplete="off">';
        ferramentas.insertBefore(rotulo, ferramentas.firstChild);
        return rotulo.querySelector('input');
    }

    function iniciar(tabela) {
        const corpo = tabela.tBodies[0];
        const cabecalhos = Array.from(tabela.querySelectorAll('thead th'));
        if (!corpo) return;

        const linhas = Array.from(corpo.rows).filter(function (linha) {
            return !linha.querySelector('.list-empty');
        });
        linhas.forEach(function (linha, i) { linha._ordemOriginal = i; });

        const aviso = document.createElement('p');
        aviso.className = 'tabela-sem-resultado';
        aviso.textContent = 'Nenhum registro encontrado.';
        aviso.hidden = linhas.length > 0 || corpo.rows.length > 0;
        tabela.closest('.table-responsive').after(aviso);

        const pesquisaveis = cabecalhos.map(function (th) { return th.dataset.searchable !== 'false'; });

        // ---- busca ----
        const card = tabela.closest('.card');
        const campo = card ? criarCampoBusca(card) : null;
        function filtrar() {
            const termo = normalizar(campo.value.trim());
            let visiveis = 0;
            linhas.forEach(function (linha) {
                const texto = Array.from(linha.cells)
                    .filter(function (_, i) { return pesquisaveis[i] !== false; })
                    .map(function (c) { return c.textContent; })
                    .join(' ');
                const mostrar = termo === '' || normalizar(texto).includes(termo);
                linha.hidden = !mostrar;
                if (mostrar) visiveis++;
            });
            aviso.hidden = visiveis > 0;
        }
        if (campo) campo.addEventListener('input', filtrar);

        // ---- ordenação ----
        let colunaAtiva = -1;
        let direcao = 0; // 1 crescente, -1 decrescente, 0 original

        function aplicarOrdem() {
            const ordenadas = linhas.slice();
            if (direcao !== 0) {
                const valores = new Map();
                linhas.forEach(function (linha) {
                    valores.set(linha, interpretar(linha.cells[colunaAtiva]));
                });
                ordenadas.sort(function (a, b) {
                    const vazioA = valores.get(a).tipo === 'vazio';
                    const vazioB = valores.get(b).tipo === 'vazio';
                    if (vazioA || vazioB) return comparar(valores.get(a), valores.get(b));
                    return direcao * comparar(valores.get(a), valores.get(b)) || a._ordemOriginal - b._ordemOriginal;
                });
            } else {
                ordenadas.sort(function (a, b) { return a._ordemOriginal - b._ordemOriginal; });
            }
            ordenadas.forEach(function (linha) { corpo.appendChild(linha); });
            cabecalhos.forEach(function (th, i) {
                th.setAttribute('aria-sort', i === colunaAtiva && direcao !== 0 ? (direcao === 1 ? 'ascending' : 'descending') : 'none');
            });
        }

        cabecalhos.forEach(function (th, indice) {
            if (th.dataset.orderable === 'false') return;
            const botao = document.createElement('button');
            botao.type = 'button';
            botao.className = 'sort-btn';
            botao.innerHTML = '<span>' + th.innerHTML + '</span>' + ICONE_ORDEM;
            th.innerHTML = '';
            th.appendChild(botao);
            th.setAttribute('aria-sort', 'none');
            botao.addEventListener('click', function () {
                if (colunaAtiva !== indice) { colunaAtiva = indice; direcao = 1; }
                else if (direcao === 1) direcao = -1;
                else if (direcao === -1) { direcao = 0; colunaAtiva = -1; }
                aplicarOrdem();
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('table.table-lista').forEach(iniciar);
    });

    // O .table-responsive corta o menu de ações da última linha; enquanto o menu
    // está aberto, o contêiner deixa de cortar.
    document.addEventListener('show.bs.dropdown', function (e) {
        const rolagem = e.target.closest('.table-responsive');
        if (rolagem) rolagem.style.overflow = 'visible';
    });
    document.addEventListener('hide.bs.dropdown', function (e) {
        const rolagem = e.target.closest('.table-responsive');
        if (rolagem) rolagem.style.overflow = '';
    });
})();
