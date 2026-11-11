/* Transforma <select data-tom-select> em dropdown com campo de busca (Tom Select).
 * Em <select multiple>, cada item escolhido vira um "chip" com botão ✕ para remover.
 *
 * Atributos opcionais no <select>:
 *   data-placeholder="..."      texto do campo de busca
 *   data-opcoes-visiveis="7"    altura da lista em opções; o resto aparece pela barra de rolagem
 *   data-buscar-pelo-valor      a busca também olha o value da opção (ex.: a sigla "PR" acha "Paraná")
 *
 * As opções aparecem na ordem do <select> (o servidor já manda ordenado).
 *
 * Requer o Tom Select carregado antes (CDN, ver company_form.html).
 * A validação (form-validation.js) marca o .ts-wrapper porque o <select> original
 * fica oculto; o Tom Select dispara "change" no <select>, o que limpa a marcação.
 */
(function () {
    "use strict";

    if (typeof TomSelect === "undefined") {
        console.error("select-search: Tom Select não foi carregado.");
        return;
    }

    // Limita a altura da lista a `quantas` opções, medindo a primeira opção desenhada
    // (a altura muda com a fonte e o tema), mais o espaçamento interno da lista
    function limitarAltura(tomSelect, quantas) {
        var lista = tomSelect.dropdown_content;
        var opcao = lista.querySelector(".option");
        if (!opcao) {
            return;
        }
        var estilo = window.getComputedStyle(lista);
        var espaco = parseFloat(estilo.paddingTop) + parseFloat(estilo.paddingBottom);
        lista.style.maxHeight = (opcao.offsetHeight * quantas + espaco) + "px";
        lista.style.overflowY = "auto";
    }

    document.querySelectorAll("select[data-tom-select]").forEach(function (selectEl) {
        var multiple = selectEl.multiple;
        var visiveis = parseInt(selectEl.dataset.opcoesVisiveis, 10);

        var tomSelect = new TomSelect(selectEl, {
            plugins: multiple ? { remove_button: { title: "Remover" } } : {},
            placeholder: selectEl.dataset.placeholder || "Busque…",
            hideSelected: true,       // item já escolhido some da lista
            closeAfterSelect: !multiple,
            dropdownParent: "body",   // evita o corte pelo overflow:hidden do card
            searchField: "buscarPeloValor" in selectEl.dataset ? ["text", "value"] : ["text"],
            render: {
                no_results: function (data, escape) {
                    return '<div class="no-results">Nenhum resultado para "' + escape(data.input) + '".</div>';
                },
            },
        });

        if (visiveis > 0) {
            tomSelect.on("dropdown_open", function () {
                limitarAltura(tomSelect, visiveis);
            });
        }
    });
})();
