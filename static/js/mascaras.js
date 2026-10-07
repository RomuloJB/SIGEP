// static/js/mascaras.js
// Aplica máscaras automaticamente com base no nome/id do campo (jQuery Mask Plugin).
// Funciona em qualquer formulário do projeto, sem precisar editar cada template:
// basta o campo ter um dos termos abaixo no nome (ex.: cpf, cnpj_cpf, phone).
// A máscara é só visual — os forms (MaskedDigitsField) removem a pontuação antes de salvar.

// A ordem importa: a primeira regra que casar vence.
// "cnpj_cpf" vem antes de "cnpj" e "cpf" para receber a máscara dinâmica de CPF/CNPJ.
var REGRAS_DE_MASCARA = [
    { termos: ['cnpj_cpf', 'cpf_cnpj'],                     mascara: 'cpf-cnpj' },
    { termos: ['cnpj'],                                     mascara: '00.000.000/0000-00' },
    { termos: ['cpf'],                                      mascara: '000.000.000-00' },
    { termos: ['cep'],                                      mascara: '00000-000' },
    { termos: ['telefone', 'celular', 'whatsapp', 'phone'], mascara: 'telefone' }
];

// Decide o formato certo (fixo ou celular) a cada tecla digitada
var comportamentoTelefone = function (val) {
    return val.replace(/\D/g, '').length === 11 ? '(00) 00000-0000' : '(00) 0000-00009';
};
var opcoesTelefone = {
    onKeyPress: function (val, e, field, options) {
        field.mask(comportamentoTelefone.apply({}, arguments), options);
    }
};

// CPF até 11 dígitos; a partir do 12º vira CNPJ (o 9 final deixa digitar o dígito extra)
var comportamentoCpfCnpj = function (val) {
    return val.replace(/\D/g, '').length <= 11 ? '000.000.000-009' : '00.000.000/0000-00';
};
var opcoesCpfCnpj = {
    onKeyPress: function (val, e, field, options) {
        field.mask(comportamentoCpfCnpj.apply({}, arguments), options);
    }
};

$(document).ready(function () {
    document.querySelectorAll('input[name]').forEach(function (input) {
        // Junta name + id numa única string para procurar o termo em qualquer um dos dois
        var chave = (input.name + ' ' + input.id).toLowerCase();
        var regra = REGRAS_DE_MASCARA.find(function (r) {
            return r.termos.some(function (termo) { return chave.includes(termo); });
        });
        if (!regra) return;

        if (regra.mascara === 'telefone') {
            $(input).mask(comportamentoTelefone, opcoesTelefone);
        } else if (regra.mascara === 'cpf-cnpj') {
            $(input).mask(comportamentoCpfCnpj, opcoesCpfCnpj);
        } else {
            $(input).mask(regra.mascara);
        }
    });
});
