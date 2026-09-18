/* Transforma <select data-tom-select> em dropdown com campo de busca (Tom Select).
 * Em <select multiple>, cada item escolhido vira um "chip" com botão ✕ para remover.
 *
 * Atributos opcionais no <select>:
 *   data-placeholder="..."   texto do campo de busca
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

    document.querySelectorAll("select[data-tom-select]").forEach(function (selectEl) {
        var multiple = selectEl.multiple;

        new TomSelect(selectEl, {
            plugins: multiple ? { remove_button: { title: "Remover" } } : {},
            placeholder: selectEl.dataset.placeholder || "Busque…",
            hideSelected: true,       // item já escolhido some da lista
            closeAfterSelect: !multiple,
            dropdownParent: "body",   // evita o corte pelo overflow:hidden do card
            render: {
                no_results: function (data, escape) {
                    return '<div class="no-results">Nenhum resultado para "' + escape(data.input) + '".</div>';
                },
            },
        });
    });
})();
