/* Máscaras de entrada aplicadas enquanto o usuário digita.
 *
 * Uso: <input data-mask="phone">     ->  (NN) NNNNN-NNNN
 *      <input data-mask="cpf">       ->  000.000.000-00
 *      <input data-mask="cnpj">      ->  00.000.000/0000-00
 *      <input data-mask="cpf-cnpj">  ->  CPF até 11 dígitos; do 12º em diante vira CNPJ
 *
 * O valor formatado é enviado como está; o servidor (cadastros.forms.MaskedDigitsField)
 * guarda só os dígitos. Funciona também para inputs inseridos depois via JS,
 * pois o listener fica no document.
 */
(function () {
    "use strict";

    function digits(raw, max) {
        return raw.replace(/\D/g, "").slice(0, max);
    }

    // Preenche um padrão (ex.: "000.000.000-00") só até onde há dígitos,
    // para a pontuação aparecer conforme o usuário digita.
    function fill(pattern, d) {
        var out = "", i = 0;
        for (var p = 0; p < pattern.length && i < d.length; p++) {
            if (pattern[p] === "0") {
                out += d[i++];
            } else {
                out += pattern[p];
            }
        }
        return out;
    }

    var MASKS = {
        phone: function (raw) {
            var d = digits(raw, 11);
            if (!d) return "";

            var out = "(" + d.slice(0, 2);
            if (d.length > 2) out += ") " + d.slice(2, 7);
            if (d.length > 7) out += "-" + d.slice(7);
            return out;
        },
        cpf: function (raw) {
            return fill("000.000.000-00", digits(raw, 11));
        },
        cnpj: function (raw) {
            return fill("00.000.000/0000-00", digits(raw, 14));
        },
        "cpf-cnpj": function (raw) {
            var d = digits(raw, 14);
            return d.length <= 11
                ? fill("000.000.000-00", d)
                : fill("00.000.000/0000-00", d);
        },
    };

    function apply(el) {
        var mask = MASKS[el.dataset.mask];
        if (!mask) return;

        var formatted = mask(el.value);
        if (formatted !== el.value) el.value = formatted;
    }

    document.addEventListener("input", function (event) {
        var el = event.target;
        if (el.dataset && el.dataset.mask) apply(el);
    }, true);

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-mask]").forEach(apply);
    });
})();
