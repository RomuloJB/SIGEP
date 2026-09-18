
(function () {
    "use strict";

    var dataEl = document.getElementById("dashboard-chart-data");
    var valueCanvas = document.getElementById("salesValueChart");
    var countCanvas = document.getElementById("salesCountChart");
    if (!dataEl || !valueCanvas || !countCanvas) return;
    if (typeof Chart === "undefined") {
        console.error("dashboard-charts: Chart.js não foi carregado.");
        return;
    }

    var data = JSON.parse(dataEl.textContent);

    /* ── formatação pt-BR ────────────────────────────────────────────────── */
    var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    var brlCompact = new Intl.NumberFormat("pt-BR", {
        style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1,
    });
    var inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

    /* ── cores: série única no verde da marca; texto/grade em tons neutros ── */
    var SERIES = "#2f7d37";
    var SERIES_WASH = "rgba(47, 125, 55, 0.10)";
    var SURFACE = "#ffffff";
    var INK_MUTED = "#6c757d";
    var GRID = "#e5e7eb";

    Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = INK_MUTED;

    function baseOptions(formatTick, formatTooltip) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: {
                legend: { display: false },   // série única: o título do card já a nomeia
                tooltip: {
                    mode: "index",
                    intersect: false,
                    displayColors: false,
                    callbacks: {
                        label: function (ctx) { return formatTooltip(ctx.parsed.y); },
                    },
                },
            },
            interaction: { mode: "index", intersect: false },
            scales: {
                x: {
                    grid: { display: false },
                    border: { color: GRID },
                    // 12 meses cabem lado a lado; sem autoSkip o mês atual nunca fica sem rótulo
                    ticks: { maxRotation: 0, autoSkip: false, font: { size: 11 } },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: GRID, drawTicks: false },
                    border: { display: false },
                    ticks: { maxTicksLimit: 5, padding: 8, callback: formatTick },
                },
            },
        };
    }

    /* ── valor de vendas (linha + área) ──────────────────────────────────── */
    var valueOptions = baseOptions(
        function (v) { return brlCompact.format(v); },
        function (v) { return "Valor: " + brl.format(v); }
    );
    // eixo sem ficar "colado" no zero quando não há vendas no período
    valueOptions.scales.y.suggestedMax = Math.max.apply(null, data.valores) > 0 ? undefined : 100;

    new Chart(valueCanvas, {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [{
                label: "Valor de vendas",
                data: data.valores,
                borderColor: SERIES,
                borderWidth: 2,
                borderJoinStyle: "round",
                borderCapStyle: "round",
                tension: 0.3,
                fill: true,
                backgroundColor: SERIES_WASH,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: SERIES,
                pointBorderColor: SURFACE,   // anel na cor da superfície
                pointBorderWidth: 2,
                pointHitRadius: 16,
            }],
        },
        options: valueOptions,
    });

    /* ── quantidade de vendas (colunas) ──────────────────────────────────── */
    var countOptions = baseOptions(
        function (v) { return inteiro.format(v); },
        function (v) { return "Pedidos: " + inteiro.format(v); }
    );
    countOptions.scales.y.ticks.precision = 0;   // só inteiros no eixo
    countOptions.scales.y.suggestedMax = Math.max.apply(null, data.quantidades) > 0 ? undefined : 5;

    new Chart(countCanvas, {
        type: "bar",
        data: {
            labels: data.labels,
            datasets: [{
                label: "Quantidade de vendas",
                data: data.quantidades,
                backgroundColor: SERIES,
                hoverBackgroundColor: "#256b2d",
                borderRadius: 4,
                borderSkipped: "start",   // arredonda só o topo; base reta na linha zero
                maxBarThickness: 24,
                categoryPercentage: 0.7,
            }],
        },
        options: countOptions,
    });

    /* ── tabela com os mesmos dados ──────────────────────────────────────── */
    var tbody = document.getElementById("chart-data-table");
    if (tbody) {
        tbody.innerHTML = data.labels.map(function (label, i) {
            return "<tr><td>" + label + "</td>" +
                '<td class="text-end">' + brl.format(data.valores[i]) + "</td>" +
                '<td class="text-end">' + inteiro.format(data.quantidades[i]) + "</td></tr>";
        }).join("");
    }
})();
