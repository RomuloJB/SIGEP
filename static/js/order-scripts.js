(function () {
    "use strict";

    /* ── referências DOM ─────────────────────────────────────────────────── */
    const itemsBody   = document.getElementById("items-body");
    const emptyRow    = document.getElementById("empty-row");
    const totalRow    = document.getElementById("total-row");
    const grandTotal  = document.getElementById("grand-total");
    const btnAdd      = document.getElementById("btn-add-product");
    const selectEl    = document.getElementById("product-select");
    const pickerError = document.getElementById("product-picker-error");
    const itemsError  = document.getElementById("items-error");
    const orderForm   = document.getElementById("order-form");

    if (!selectEl || !orderForm) return;   // sai se o template não estiver presente
    if (typeof TomSelect === "undefined") {
        console.error("order-scripts: Tom Select não foi carregado.");
        return;
    }

    /* ── helpers ─────────────────────────────────────────────────────────── */
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

    /* ── dropdown de produtos (Tom Select) ───────────────────────────────── */
    // Tom Select copia os data-* de cada <option> para o objeto da opção
    // (data-price -> price, data-price-br -> priceBr, ...). Geramos aqui o
    // valor no formato BR para a busca aceitar tanto "12.50" quanto "12,50".
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

    // marca/desmarca o produto no dropdown conforme ele entra ou sai do pedido
    function setOptionAdded(id, added) {
        const data = productSelect.options[id];
        if (!data) return;
        productSelect.updateOption(id, Object.assign({}, data, {
            added: added,
            disabled: added || (parseInt(data.stock, 10) || 0) <= 0,
        }));
    }

    /* ── adiciona linha de item na tabela ────────────────────────────────── */
    function addProductRow(product) {
        if (itemsBody.querySelector('tr[data-product-id="' + product.id + '"]')) {
            alert('"' + product.name + '" já foi adicionado. Ajuste a quantidade na linha existente.');
            return;
        }

        const price     = parseFloat(product.price) || 0;
        const stock     = parseInt(product.stock, 10) || 0;
        const lineTotal = price * 1; // qty inicial = 1, desconto inicial = 0

        const tr = document.createElement("tr");
        tr.dataset.productId = product.id;
        tr.dataset.lineTotal = lineTotal;
        tr.dataset.valid = "true";

        tr.innerHTML =
            '<td>' +
                '<div class="fw-semibold">' + esc(product.name) + '</div>' +
                '<small class="text-muted">' + esc(product.sku || "") + (product.sku ? " · " : "") + esc(product.unit) + '</small>' +
                '<input type="hidden" name="product_id[]" value="' + esc(product.id) + '">' +
            '</td>' +
            '<td>' +
                '<span class="badge ' + (stock <= 5 ? 'bg-warning text-dark' : 'bg-secondary') + '">' + stock + '</span>' +
            '</td>' +
            '<td>' +
                '<input type="number" name="quantity[]"' +
                       ' class="form-control form-control-sm qty-input"' +
                       ' min="1" max="' + stock + '" value="1"' +
                       ' style="width:80px">' +
            '</td>' +
            '<td class="text-end">' + fmt(price) + '</td>' +
            '<td>' +
                '<input type="number" name="discount[]"' +
                       ' class="form-control form-control-sm discount-input"' +
                       ' min="0" step="0.01" value="0.00"' +
                       ' style="width:100px">' +
            '</td>' +
            '<td class="text-end fw-semibold line-total-cell">' + fmt(lineTotal) + '</td>' +
            '<td class="text-center">' +
                '<button type="button" class="btn btn-sm btn-outline-danger btn-remove" title="Remover">' +
                    '<i class="fas fa-trash"></i>' +
                '</button>' +
            '</td>';

        /* linha de aviso (vermelho), fora da <table> não dá — usamos um <tr> auxiliar */
        const warningRow = document.createElement("tr");
        warningRow.className = "warning-row d-none";
        warningRow.innerHTML = '<td colspan="7" class="text-danger small py-1 warning-text"></td>';

        const qtyInput  = tr.querySelector(".qty-input");
        const discInput = tr.querySelector(".discount-input");

        function updateRow() {
            const qty      = parseInt(qtyInput.value, 10);
            const discount = parseFloat(discInput.value) || 0;
            const subtotal = (isNaN(qty) ? 0 : qty) * price;

            let warning = "";
            if (isNaN(qty) || qty <= 0) {
                warning = "A quantidade deve ser maior que zero.";
            } else if (qty > stock) {
                warning = "Estoque insuficiente! Disponível: " + stock + ".";
            } else if (discount < 0) {
                warning = "O desconto não pode ser negativo.";
            } else if (discount > subtotal) {
                warning = "O desconto não pode ser maior que o valor do item.";
            }

            const total = warning ? 0 : Math.max(subtotal - discount, 0);
            tr.querySelector(".line-total-cell").textContent = fmt(total);
            tr.dataset.lineTotal = total;

            qtyInput.classList.toggle("is-invalid", !!warning);
            warningRow.querySelector(".warning-text").textContent = warning;
            warningRow.classList.toggle("d-none", !warning);
            tr.dataset.valid = warning ? "false" : "true";

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
        showItemsError("");
        updateVisibility();
        recalcTotal();
    }

    /* ── botão "Adicionar produto" ───────────────────────────────────────── */
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

    // Enter no campo de busca: com o dropdown aberto o Tom Select seleciona a opção
    // (e marca defaultPrevented); fechado, adiciona o produto em vez de submeter o form.
    productSelect.control_input.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" || e.defaultPrevented) return;
        e.preventDefault();
        if (productSelect.getValue()) addSelectedProduct();
    });

    /* ── validação antes de submeter ─────────────────────────────────────── */
    // O form-validation.js (fase de captura) já validou os campos do pedido e
    // limpou o resumo; aqui só entra a regra dos itens, somada ao mesmo resumo.
    orderForm.addEventListener("submit", function (e) {
        const rows = itemsBody.querySelectorAll("tr[data-product-id]");

        let message = "";
        if (rows.length === 0) {
            message = "Adicione pelo menos um produto ao pedido antes de salvar.";
        } else if (Array.prototype.some.call(rows, function (row) { return row.dataset.valid === "false"; })) {
            message = "Corrija os itens destacados em vermelho antes de salvar.";
        }

        showItemsError(message);
        if (!message) return;

        e.preventDefault();
        if (window.FormValidation) {
            window.FormValidation.addError(orderForm, "Itens do pedido: " + message);
        }
    });

})();
