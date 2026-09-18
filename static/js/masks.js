/* Máscaras de entrada aplicadas enquanto o usuário digita.
 *
 * Uso: <input data-mask="phone">   ->  (NN) NNNNN-NNNN
 *
 * O valor formatado é enviado como está; o servidor (cadastros.forms.PhoneField)
 * guarda só os dígitos. Funciona também para inputs inseridos depois via JS,
 * pois o listener fica no document.
 */
(function () {
    "use strict";

    var MASKS = {
        phone: function (raw) {
            var d = raw.replace(/\D/g, "").slice(0, 11);
            if (!d) return "";

            var out = "(" + d.slice(0, 2);
            if (d.length > 2) out += ") " + d.slice(2, 7);
            if (d.length > 7) out += "-" + d.slice(7);
            return out;
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
