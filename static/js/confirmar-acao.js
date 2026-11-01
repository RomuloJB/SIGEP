// Confirma com o Bootbox os formulários de ação (ex.: mudar o status do pedido)
// antes de enviar o POST. Uso:
//   <form method="post" class="form-confirmar" data-titulo="Aprovar"
//         data-mensagem="Mudar o pedido nº 3 para Aprovado?" data-botao="Aprovar"
//         data-classe="btn-success">
// A mensagem é texto: entra escapada no modal.
(function () {
    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto || '';
        return div.innerHTML;
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.classList.contains('form-confirmar')) return;
        if (typeof bootbox === 'undefined') return; // sem a CDN, envia direto

        e.preventDefault();
        bootbox.confirm({
            title: form.dataset.titulo || 'Confirmar',
            message: '<p class="mb-0">' + escapeHtml(form.dataset.mensagem) + '</p>',
            buttons: {
                confirm: { label: form.dataset.botao || 'Confirmar', className: form.dataset.classe || 'btn-primary' },
                cancel: { label: 'Voltar', className: 'btn-outline-secondary' },
            },
            callback: function (confirmado) {
                if (confirmado) form.submit(); // só envia de fato depois da confirmação
            },
        });
    });
})();
