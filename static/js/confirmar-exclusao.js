(function () {
    var PALAVRA = 'excluir';

    var BOTOES = {
        confirm: { label: 'Sim, excluir', className: 'btn-danger' },
        cancel: { label: 'Cancelar', className: 'btn-outline-secondary' },
    };

    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto || '';
        return div.innerHTML;
    }

    function mensagemBase(form) {
        var tipo = escapeHtml(form.dataset.tipo || 'o registro');
        var nome = form.dataset.nome ? ' <strong>' + escapeHtml(form.dataset.nome) + '</strong>' : '';
        return '<p class="mb-2">Tem certeza que deseja excluir ' + tipo + nome + '?</p>' +
            '<p class="text-danger fw-bold mb-0">Essa ação não pode ser desfeita.</p>';
    }

    function confirmarSimples(form, titulo) {
        bootbox.confirm({
            title: titulo,
            message: mensagemBase(form),
            buttons: BOTOES,
            callback: function (confirmado) {
                if (confirmado) form.submit(); // só envia de fato depois do "Sim, excluir"
            },
        });
    }

    function confirmarDigitando(form, titulo) {
        var confere = function (valor) { return valor.trim().toLowerCase() === PALAVRA; };

        var caixa = bootbox.dialog({
            title: titulo,
            message: mensagemBase(form) +
                '<hr>' +
                '<label class="form-label" for="bootbox-confirmacao">' +
                    'Para confirmar, digite <strong>' + PALAVRA + '</strong> abaixo:' +
                '</label>' +
                '<input type="text" class="form-control" id="bootbox-confirmacao" autocomplete="off" spellcheck="false">',
            onEscape: true,
            buttons: {
                cancel: BOTOES.cancel,
                confirm: {
                    label: BOTOES.confirm.label,
                    className: BOTOES.confirm.className,
                    callback: function () {
                        var valor = campo.val();
                        if (!confere(valor)) return false; // mantém o modal aberto
                        form.querySelector('input[name="confirmacao"]').value = valor;
                        form.submit();
                    },
                },
            },
        });

        var campo = caixa.find('#bootbox-confirmacao');
        var botao = caixa.find('[data-bb-handler="confirm"]').prop('disabled', true);

        campo.on('input', function () {
            botao.prop('disabled', !confere(campo.val()));
        });
        campo.on('keydown', function (e) {
            if (e.key === 'Enter' && confere(campo.val())) botao.trigger('click');
        });
        caixa.on('shown.bs.modal', function () { campo.trigger('focus'); });
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.classList.contains('form-excluir')) return;

        e.preventDefault();
        if (typeof bootbox === 'undefined') {
            window.location.href = form.action;
            return;
        }

        var titulo = form.dataset.titulo || 'Excluir registro';
        if (form.dataset.confirmarDigitando === 'true') {
            confirmarDigitando(form, titulo);
        } else {
            confirmarSimples(form, titulo);
        }
    });
})();
