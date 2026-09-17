/* Validação de formulários no navegador (Constraint Validation API) com
 * mensagens em português, no mesmo formato que o crispy-forms usa para os
 * erros vindos do servidor (.is-invalid + .invalid-feedback), mais um
 * resumo (alert) no topo do formulário.
 *
 * Uso: <form class="needs-validation" novalidate> ... </form>
 *
 * Controles dentro de um elemento com [data-no-validate] são ignorados —
 * o script da própria página cuida deles (ex.: itens do pedido).
 *
 * API (window.FormValidation):
 *   validate(form)            -> true/false; marca os campos e monta o resumo
 *   addError(form, message)   -> acrescenta uma linha ao resumo do formulário
 *   clearErrors(form)         -> remove marcações e resumo
 */
(function () {
    "use strict";

    var SUMMARY_CLASS = "form-validation-summary";
    var SUMMARY_TITLE = "Não foi possível salvar. Corrija os itens abaixo:";

    /* ── mensagens ───────────────────────────────────────────────────────── */
    function decimalPlaces(step) {
        var parts = String(step || "").split(".");
        return parts.length > 1 ? parts[1].length : 0;
    }

    function messageFor(el) {
        var v = el.validity;

        if (v.valueMissing) return "Este campo é obrigatório.";
        if (v.typeMismatch) {
            if (el.type === "email") return "Informe um e-mail válido.";
            if (el.type === "url") return "Informe uma URL válida.";
            return "Informe um valor válido.";
        }
        if (v.badInput) return "Informe um número válido.";
        if (v.rangeUnderflow) return "O valor deve ser maior ou igual a " + el.min + ".";
        if (v.rangeOverflow) return "O valor deve ser menor ou igual a " + el.max + ".";
        if (v.stepMismatch) {
            var places = decimalPlaces(el.step);
            return places
                ? "Informe um valor com no máximo " + places + " casas decimais."
                : "Informe um número inteiro.";
        }
        if (v.tooShort) return "Informe pelo menos " + el.minLength + " caracteres.";
        if (v.tooLong) return "Informe no máximo " + el.maxLength + " caracteres.";
        if (v.patternMismatch) return el.title || "O valor informado não está no formato esperado.";

        return el.validationMessage || "Valor inválido.";
    }

    function labelFor(el) {
        var label = el.id ? el.form.querySelector('label[for="' + el.id + '"]') : null;
        if (!label) {
            var wrapper = el.closest(".mb-3");
            label = wrapper ? wrapper.querySelector("label, legend") : null;
        }
        if (!label) return el.name || "Campo";
        return label.textContent.replace("*", "").trim();
    }

    /* ── marcação dos campos ─────────────────────────────────────────────── */
    function feedbackFor(el, create) {
        // Reaproveita o .invalid-feedback que o crispy renderiza logo após o campo
        var fb = el.nextElementSibling;
        if (fb && fb.classList.contains("invalid-feedback")) return fb;
        if (!create) return null;

        fb = document.createElement("div");
        fb.className = "invalid-feedback";
        el.insertAdjacentElement("afterend", fb);
        return fb;
    }

    function markControl(el, message) {
        el.classList.add("is-invalid");
        el.setAttribute("aria-invalid", "true");

        var fb = feedbackFor(el, true);
        fb.innerHTML = "<strong></strong>";
        fb.firstChild.textContent = message;
    }

    function unmarkControl(el) {
        // O .invalid-feedback some sozinho via CSS quando o campo perde .is-invalid
        el.classList.remove("is-invalid");
        el.removeAttribute("aria-invalid");
    }

    function isValidatable(el) {
        return el.willValidate && !el.closest("[data-no-validate]");
    }

    function validatableControls(form) {
        return Array.prototype.filter.call(form.elements, isValidatable);
    }

    /* ── resumo no topo do formulário ────────────────────────────────────── */
    function summaryFor(form, create) {
        var box = form.querySelector("." + SUMMARY_CLASS);
        if (box || !create) return box;

        box = document.createElement("div");
        box.className = "alert alert-danger " + SUMMARY_CLASS;
        box.setAttribute("role", "alert");
        box.innerHTML = '<p class="fw-semibold mb-1"></p><ul class="mb-0"></ul>';
        box.firstChild.textContent = SUMMARY_TITLE;
        form.insertBefore(box, form.firstChild);
        return box;
    }

    function addSummaryLine(form, message, controlId) {
        var li = document.createElement("li");
        li.textContent = message;
        if (controlId) li.dataset.controlId = controlId;
        summaryFor(form, true).querySelector("ul").appendChild(li);
    }

    function removeSummaryLine(form, controlId) {
        var box = summaryFor(form, false);
        if (!box) return;

        box.querySelectorAll('li[data-control-id="' + controlId + '"]').forEach(function (li) {
            li.remove();
        });
        if (!box.querySelector("li")) box.remove();
    }

    /* ── API pública ─────────────────────────────────────────────────────── */
    var api = {
        clearErrors: function (form) {
            var box = summaryFor(form, false);
            if (box) box.remove();
            validatableControls(form).forEach(unmarkControl);
        },

        addError: function (form, message) {
            addSummaryLine(form, message, null);
        },

        validate: function (form) {
            api.clearErrors(form);

            var invalid = validatableControls(form).filter(function (el) {
                return !el.checkValidity();
            });

            invalid.forEach(function (el) {
                var message = messageFor(el);
                markControl(el, message);
                addSummaryLine(form, labelFor(el) + ": " + message, el.id);
            });

            if (invalid.length) {
                var first = invalid[0];
                first.scrollIntoView({ block: "center", behavior: "smooth" });
                first.focus({ preventScroll: true });
            }

            return invalid.length === 0;
        },
    };

    window.FormValidation = api;

    /* ── eventos ─────────────────────────────────────────────────────────── */
    // Fase de captura: roda antes dos listeners das páginas (que podem
    // acrescentar erros próprios ao resumo) e do botão "Aguarde".
    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.classList.contains("needs-validation")) return;

        if (!api.validate(form)) event.preventDefault();
    }, true);

    // Limpa a marcação do campo assim que o usuário o corrige
    function onFieldChange(event) {
        var el = event.target;
        if (!el.form || !el.form.classList.contains("needs-validation")) return;
        if (!el.classList.contains("is-invalid") || !isValidatable(el)) return;

        if (el.checkValidity()) {
            unmarkControl(el);
            removeSummaryLine(el.form, el.id);
        }
    }

    document.addEventListener("input", onFieldChange, true);
    document.addEventListener("change", onFieldChange, true);
})();
