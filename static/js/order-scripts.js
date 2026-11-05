(function () {
    "use strict";

    const itemsBody   = document.getElementById("items-body");
    const emptyRow    = document.getElementById("empty-row");
    const totalRow    = document.getElementById("total-row");
    const grandTotal  = document.getElementById("grand-total");
    const btnAdd      = document.getElementById("btn-add-product");
    const selectEl    = document.getElementById("product-select");
    const pickerError = document.getElementById("product-picker-error");
    const itemsError  = document.getElementById("items-error");
    const orderForm   = document.getElementById("order-form");

    if (!selectEl || !orderForm) return;
    if (typeof TomSelect === "undefined") {
        console.error("order-scripts: Tom Select não foi carregado.");
        return;
    }

    function fmt(value) {
        return "R$ " + Number(value).toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function esc(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function recalcTotal() {
        let total = 0;
        itemsBody.querySelectorAll("tr[data-product-id]").forEach(function (row) {
            total += parseFloat(row.dataset.lineTotal || 0);
        });
        grandTotal.textContent = fmt(total);
    }

    function updateVisibility() {
        const hasRows = itemsBody.querySelectorAll("tr[data-product-id]").length > 0;
        emptyRow.classList.toggle("d-none", hasRows);
        totalRow.classList.toggle("d-none", !hasRows);
    }

    function showPickerError(message) {
        pickerError.textContent = message;
        pickerError.classList.toggle("d-none", !message);
    }

    function showItemsError(message) {
        itemsError.textContent = message;
        itemsError.classList.toggle("d-none", !message);
    }

    function stockBadge(stock) {
        if (stock <= 0) return '<span class="badge bg-danger">Sem estoque</span>';
        const cls = stock <= 5 ? "bg-warning text-dark" : "bg-secondary";
        return '<span class="badge ' + cls + '">Estoque: ' + stock + '</span>';
    }

    selectEl.querySelectorAll("option").forEach(function (opt) {
        if (!opt.value) return;
        opt.dataset.priceBr = (parseFloat(opt.dataset.price) || 0).toFixed(2).replace(".", ",");
    });

    const productSelect = new TomSelect(selectEl, {
        maxOptions: 100,
        searchField: ["value", "sku", "name", "price", "priceBr"],
        dropdownParent: "body",   // evita o corte pelo overflow:hidden do card
        render: {
            option: function (data, escape) {
                const stock = parseInt(data.stock, 10) || 0;
                const meta  = ["#" + escape(data.value)];
                if (data.sku) meta.push(escape(data.sku));
                if (data.unit) meta.push(escape(data.unit));

                return '<div class="product-option">' +
                    '<div class="product-option-main">' +
                        '<div class="product-option-name">' + escape(data.name) + '</div>' +
                        '<div class="product-option-meta">' + meta.join(" · ") + '</div>' +
                    '</div>' +
                    '<div class="product-option-side">' +
                        '<div class="product-option-price">' + fmt(data.price) + '</div>' +
                        (data.added ? '<span class="badge bg-success">Já no pedido</span>' : stockBadge(stock)) +
                    '</div>' +
                '</div>';
            },
            item: function (data, escape) {
                return '<div>' +
                    (data.sku ? '<span class="text-muted">' + escape(data.sku) + '</span> — ' : '') +
                    escape(data.name) +
                    ' <span class="text-muted">(' + fmt(data.price) + ')</span>' +
                '</div>';
            },
            no_results: function (data, escape) {
                return '<div class="no-results">Nenhum produto encontrado para "' + escape(data.input) + '".</div>';
            },
        },
        onChange: function () { showPickerError(""); },
    });

    function setOptionAdded(id, added) {
        const data = productSelect.options[id];
        if (!data) return;
        productSelect.updateOption(id, Object.assign({}, data, {
            added: added,
            disabled: added || (parseInt(data.stock, 10) || 0) <= 0,
        }));
    }

    function addProductRow(product) {
        if (itemsBody.querySelector('tr[data-product-id="' + product.id + '"]')) {
            const nome = document.createElement('strong');
            nome.textContent = product.name; // nome vem do banco: entra como texto, não HTML
            bootbox.alert({
                title: 'Produto já adicionado',
                message: nome.outerHTML + ' já está no pedido. Ajuste a quantidade na linha existente.',
            });
            return;
        }

        const price    = parseFloat(product.price) || 0;
        const stock    = parseInt(product.stock, 10) || 0;
        // Linha nova começa com qtd 1 e sem desconto; itens iniciais trazem os seus
        const qty      = product.quantity != null ? parseInt(product.quantity, 10) : 1;
        const discount = parseFloat(product.discount) || 0;

        const tr = document.createElement("tr");
        tr.dataset.productId = product.id;

        tr.innerHTML =
            '<td>' +
                '<div class="fw-semibold">' + esc(product.name) + '</div>' +
                '<small class="text-muted">' + esc(product.sku || "") + (product.sku ? " · " : "") + esc(product.unit) + '</small>' +
                '<input type="hidden" name="product_id[]" value="' + esc(product.id) + '">' +
            '</td>' +
            '<td>' +
                '<span class="' + (stock <= 5 ? 'badge-soft-warning' : 'badge-soft-neutral') + '">' + stock + '</span>' +
            '</td>' +
            '<td>' +
                '<input type="number" name="quantity[]"' +
                       ' class="form-control form-control-sm qty-input"' +
                       ' min="1" max="' + stock + '" value="' + (isNaN(qty) ? "" : qty) + '"' +
                       ' style="width:80px">' +
            '</td>' +
            '<td class="text-end">' + fmt(price) + '</td>' +
            '<td>' +
                '<input type="number" name="discount[]"' +
                       ' class="form-control form-control-sm discount-input"' +
                       ' min="0" step="0.01" value="' + discount.toFixed(2) + '"' +
                       ' style="width:100px">' +
            '</td>' +
            '<td class="text-end fw-semibold line-total-cell"></td>' +
            '<td class="text-center">' +
                '<button type="button" class="btn btn-sm btn-icon btn-soft-danger btn-remove" title="Remover" aria-label="Remover produto">' +
                    '<i class="fas fa-trash"></i>' +
                '</button>' +
            '</td>';

        const warningRow = document.createElement("tr");
        warningRow.className = "warning-row d-none";
        warningRow.innerHTML = '<td colspan="7" class="text-danger small py-1 warning-text"></td>';

        const qtyInput  = tr.querySelector(".qty-input");
        const discInput = tr.querySelector(".discount-input");

        function updateRow() {
            const qty      = parseInt(qtyInput.value, 10);
            const discount = parseFloat(discInput.value) || 0;
            const subtotal = (isNaN(qty) ? 0 : qty) * price;

            // erro: valor inválido, impede qualquer salvamento.
            // aviso de estoque: o rascunho pode ser salvo; só o envio exige estoque.
            let erro = "";
            let avisoEstoque = "";
            if (isNaN(qty) || qty <= 0) {
                erro = "A quantidade deve ser maior que zero.";
            } else if (discount < 0) {
                erro = "O desconto não pode ser negativo.";
            } else if (discount > subtotal) {
                erro = "O desconto não pode ser maior que o valor do item.";
            } else if (qty > stock) {
                avisoEstoque = "Estoque insuficiente! Disponível: " + stock + ". Dá para salvar em rascunho, mas só enviar com estoque.";
            }

            const total = erro ? 0 : Math.max(subtotal - discount, 0);
            tr.querySelector(".line-total-cell").textContent = fmt(total);
            tr.dataset.lineTotal = total;

            const warning = erro || avisoEstoque;
            qtyInput.classList.toggle("is-invalid", !!warning);
            warningRow.querySelector(".warning-text").textContent = warning;
            warningRow.classList.toggle("d-none", !warning);
            tr.dataset.valid = erro ? "false" : "true";
            tr.dataset.semEstoque = avisoEstoque ? "true" : "false";

            showItemsError("");
            recalcTotal();
        }

        qtyInput.addEventListener("input", updateRow);
        discInput.addEventListener("input", updateRow);

        tr.querySelector(".btn-remove").addEventListener("click", function () {
            tr.remove();
            warningRow.remove();
            setOptionAdded(product.id, false);
            showItemsError("");
            updateVisibility();
            recalcTotal();
        });

        itemsBody.appendChild(tr);
        itemsBody.appendChild(warningRow);
        setOptionAdded(product.id, true);
        updateVisibility();
        updateRow(); // calcula o total da linha e já avisa estoque/desconto inválidos
    }

    function addSelectedProduct() {
        const id = productSelect.getValue();
        if (!id) {
            showPickerError("Selecione um produto na lista antes de adicionar.");
            productSelect.focus();
            return;
        }

        const data = productSelect.options[id];
        addProductRow({
            id    : id,
            name  : data.name,
            sku   : data.sku,
            unit  : data.unit,
            price : data.price,
            stock : data.stock,
        });
        productSelect.clear(true);
    }

    btnAdd.addEventListener("click", addSelectedProduct);

    // Itens já preenchidos: pedido duplicado ou formulário devolvido com erro
    const initialItems = document.getElementById("itens-iniciais");
    if (initialItems) {
        JSON.parse(initialItems.textContent).forEach(function (item) {
            const data = productSelect.options[item.product_id];
            if (!data) return; // produto que não é mais da empresa ativa
            if (itemsBody.querySelector('tr[data-product-id="' + data.value + '"]')) return;
            addProductRow({
                id       : data.value,
                name     : data.name,
                sku      : data.sku,
                unit     : data.unit,
                price    : data.price,
                stock    : data.stock,
                quantity : item.quantity,
                discount : item.discount,
            });
        });
    }

    productSelect.control_input.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" || e.defaultPrevented) return;
        e.preventDefault();
        if (productSelect.getValue()) addSelectedProduct();
    });

    orderForm.addEventListener("submit", function (e) {
        const rows = itemsBody.querySelectorAll("tr[data-product-id]");
        // Botão clicado: "rascunho" ou "enviar". Enter num campo usa o primeiro botão (rascunho)
        const submitter = e.submitter;
        const acao = submitter && submitter.name === "acao" ? submitter.value : "rascunho";

        function algumaLinha(campo, valor) {
            return Array.prototype.some.call(rows, function (row) { return row.dataset[campo] === valor; });
        }

        let message = "";
        if (rows.length === 0) {
            message = "Adicione pelo menos um produto ao pedido antes de salvar.";
        } else if (algumaLinha("valid", "false")) {
            message = "Corrija os itens destacados em vermelho antes de salvar.";
        } else if (acao === "enviar" && algumaLinha("semEstoque", "true")) {
            message = "Há itens sem estoque suficiente. Ajuste as quantidades ou salve em rascunho.";
        }

        showItemsError(message);
        if (message) {
            e.preventDefault();
            if (window.FormValidation) {
                window.FormValidation.addError(orderForm, "Itens do pedido: " + message);
            }
            return;
        }

        // O model.html desabilita o botão clicado ("Aguarde"), e o navegador não envia
        // o valor de botão desabilitado: a ação segue num campo oculto
        let campoAcao = orderForm.querySelector('input[type="hidden"][name="acao"]');
        if (!campoAcao) {
            campoAcao = document.createElement("input");
            campoAcao.type = "hidden";
            campoAcao.name = "acao";
            orderForm.appendChild(campoAcao);
        }
        campoAcao.value = acao;
    });

    // "Cancelar" sai sem salvar; se algo foi preenchido, confirma antes de descartar
    let alterado = false;
    orderForm.addEventListener("input", function () { alterado = true; });
    orderForm.addEventListener("change", function () { alterado = true; });
    itemsBody.addEventListener("click", function (e) {
        if (e.target.closest(".btn-remove")) alterado = true;
    });
    btnAdd.addEventListener("click", function () { alterado = true; });

    document.querySelectorAll(".btn-cancelar-pedido").forEach(function (link) {
        link.addEventListener("click", function (e) {
            if (!alterado || typeof bootbox === "undefined") return;
            e.preventDefault();
            bootbox.confirm({
                title: "Descartar pedido",
                message: "Sair sem salvar? O que foi preenchido neste pedido será perdido.",
                buttons: {
                    confirm: { label: "Sim, descartar", className: "btn-danger" },
                    cancel: { label: "Continuar editando", className: "btn-outline-secondary" },
                },
                callback: function (confirmado) {
                    if (confirmado) window.location.href = link.href;
                },
            });
        });
    });

})();
