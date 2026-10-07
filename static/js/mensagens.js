// Mostra as mensagens do Django (django.contrib.messages) como bootbox.alert.
// O model.html só inclui este arquivo quando há mensagens, dentro de #mensagens-django;
// o texto já vem escapado pelo template, por isso é lido com innerHTML.
(function () {
    var TITULOS = {
        error: 'Não foi possível concluir',
        warning: 'Atenção',
        success: 'Sucesso',
        info: 'Aviso',
        debug: 'Aviso',
    };

    var caixa = document.getElementById('mensagens-django');
    if (!caixa || typeof bootbox === 'undefined') return;

    // Uma mensagem por vez: a próxima abre quando a anterior for fechada
    var fila = Array.prototype.slice.call(caixa.children);

    function proxima() {
        var item = fila.shift();
        if (!item) return;
        bootbox.alert({
            title: TITULOS[item.dataset.nivel] || 'Aviso',
            message: item.innerHTML,
            callback: proxima,
        });
    }

    proxima();
})();
