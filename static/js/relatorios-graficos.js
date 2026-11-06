// Gráficos do painel gerencial (cadastros/management_report.html).
// Os dados vêm do Django em <script id="relatorios-dados" type="application/json"> e
// são montados em cadastros/relatorios.py. Cada gráfico mostra "sem dados" quando
// não há nada a exibir, em vez de um canvas vazio.
(function () {
    "use strict";

    var dadosEl = document.getElementById("relatorios-dados");
    if (!dadosEl) return;
    if (typeof Chart === "undefined") {
        console.error("relatorios-graficos: Chart.js não foi carregado.");
        return;
    }

    var dados = JSON.parse(dadosEl.textContent);

    var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    var brlCompacto = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
    var inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

    // Paleta do SIGEP: verde da marca primeiro, depois azul, dourado, vermelho e neutros
    var PALETA = ["#198754", "#2563c9", "#b7791f", "#c93c3c", "#5d6b63", "#2a9d8f", "#7c5cbf", "#d97b29", "#8aa399", "#a33b7a"];
    var COR_STATUS = {
        digitacao: "#8aa399",
        pendente: "#b7791f",
        aprovado: "#198754",
        rejeitado: "#c93c3c",
        cancelado: "#5d6b63",
    };
    var INK_MUTED = "#66756d";
    var GRID = "#e1e8e3";

    Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = INK_MUTED;

    function semDados(canvas, serie) {
        var total = serie.valores.reduce(function (soma, v) { return soma + v; }, 0);
        if (serie.labels.length && total > 0) return false;
        canvas.closest(".chart-area").hidden = true;
        canvas.closest(".card-body").querySelector(".grafico-vazio").hidden = false;
        return true;
    }

    function pegar(id, chave) {
        var canvas = document.getElementById(id);
        var serie = dados[chave];
        if (!canvas || !serie || semDados(canvas, serie)) return null;
        return { canvas: canvas, serie: serie };
    }

    // Rosca: composição (partes de um todo)
    function rosca(id, chave, formatar, cores) {
        var g = pegar(id, chave);
        if (!g) return;
        new Chart(g.canvas, {
            type: "doughnut",
            data: {
                labels: g.serie.labels,
                datasets: [{
                    data: g.serie.valores,
                    backgroundColor: cores || PALETA,
                    borderColor: "#ffffff",
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "right", labels: { boxWidth: 12, boxHeight: 12, padding: 14 } },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                var pct = total ? (ctx.parsed * 100 / total).toFixed(1).replace(".", ",") : "0";
                                return ctx.label + ": " + formatar(ctx.parsed) + " (" + pct + "%)";
                            },
                        },
                    },
                },
            },
        });
    }

    // Barras: comparação entre categorias (horizontal quando os rótulos são longos)
    function barras(id, chave, opcoes) {
        var g = pegar(id, chave);
        if (!g) return;
        var horizontal = !!opcoes.horizontal;
        var valorEixo = horizontal ? "x" : "y";
        var escalaValor = {
            beginAtZero: true,
            grid: { color: GRID, drawTicks: false },
            border: { display: false },
            ticks: { maxTicksLimit: 5, padding: 6, callback: function (v) { return opcoes.eixo(v); } },
        };
        var escalaRotulo = {
            grid: { display: false },
            border: { color: GRID },
            ticks: { autoSkip: false, maxRotation: 0 },
        };
        var escalas = {};
        escalas[valorEixo] = escalaValor;
        escalas[horizontal ? "y" : "x"] = escalaRotulo;

        new Chart(g.canvas, {
            type: "bar",
            data: {
                labels: g.serie.labels,
                datasets: [{
                    data: g.serie.valores,
                    backgroundColor: opcoes.cor,
                    hoverBackgroundColor: opcoes.corHover,
                    borderRadius: 4,
                    maxBarThickness: 28,
                }],
            },
            options: {
                indexAxis: horizontal ? "y" : "x",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        displayColors: false,
                        callbacks: {
                            label: function (ctx) { return opcoes.tooltip(ctx.parsed[valorEixo]); },
                        },
                    },
                },
                scales: escalas,
            },
        });
    }

    // Funil de status: cada status na sua cor (a ordem é a do ciclo de vida)
    (function () {
        var g = pegar("grafico-status", "status");
        if (!g) return;
        new Chart(g.canvas, {
            type: "bar",
            data: {
                labels: g.serie.labels,
                datasets: [{
                    data: g.serie.valores,
                    backgroundColor: g.serie.chaves.map(function (c) { return COR_STATUS[c]; }),
                    borderRadius: 4,
                    maxBarThickness: 48,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { displayColors: false, callbacks: { label: function (ctx) { return inteiro.format(ctx.parsed.y) + " pedidos"; } } },
                },
                scales: {
                    x: { grid: { display: false }, border: { color: GRID } },
                    y: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: GRID, drawTicks: false }, border: { display: false } },
                },
            },
        });
    })();

    rosca("grafico-pagamento", "pagamento", function (v) { return brl.format(v); });

    barras("grafico-produtos", "produtos", {
        horizontal: true, cor: "#198754", corHover: "#147a4a",
        eixo: function (v) { return brlCompacto.format(v); },
        tooltip: function (v) { return brl.format(v); },
    });
    barras("grafico-clientes", "clientes", {
        horizontal: true, cor: "#2563c9", corHover: "#1f54ad",
        eixo: function (v) { return brlCompacto.format(v); },
        tooltip: function (v) { return brl.format(v); },
    });
    barras("grafico-representantes", "representantes", {
        horizontal: false, cor: "#b7791f", corHover: "#9f6a1b",
        eixo: function (v) { return brlCompacto.format(v); },
        tooltip: function (v) { return brl.format(v); },
    });
    barras("grafico-uf", "uf", {
        horizontal: false, cor: "#2a9d8f", corHover: "#23867a",
        eixo: function (v) { return brlCompacto.format(v); },
        tooltip: function (v) { return brl.format(v); },
    });
    barras("grafico-estoque", "estoque", {
        horizontal: true, cor: "#c93c3c", corHover: "#b23232",
        eixo: function (v) { return inteiro.format(v); },
        tooltip: function (v) { return inteiro.format(v) + " un."; },
    });
})();
