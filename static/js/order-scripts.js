(function () {
    "use strict";
 
    /* ── referências DOM ─────────────────────────────────────────────────── */
    const itemsBody    = document.getElementById("items-body");
    const emptyRow     = document.getElementById("empty-row");
    const totalRow     = document.getElementById("total-row");
    const grandTotal   = document.getElementById("grand-total");
    const btnAdd       = document.getElementById("btn-add-product");
    const searchInput  = document.getElementById("product-search");
    const orderForm    = document.getElementById("order-form");
    const modalEl      = document.getElementById("productModal");
 
    if (!modalEl) return;   // sai se o template não estiver presente
    const productModal = new bootstrap.Modal(modalEl);
 
    /* ── helpers ─────────────────────────────────────────────────────────── */
    function fmt(value) {
        return "R$ " + Number(value).toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
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
 
    /* ── adiciona linha de item na tabela ────────────────────────────────── */
    function addProductRow(product) {
        if (itemsBody.querySelector('tr[data-product-id="' + product.id + '"]')) {
            alert('"' + product.name + '" já foi adicionado. Ajuste a quantidade na linha existente.');
            productModal.hide();
            return;
        }

    const price     = parseFloat(product.price) || 0;
    const stock     = parseInt(product.stock)   || 0;
    const lineTotal = price * 1; // qty inicial = 1, desconto inicial = 0

    const tr = document.createElement("tr");
    tr.dataset.productId = product.id;
    tr.dataset.lineTotal = lineTotal;
    tr.dataset.valid = "true";

    tr.innerHTML =
        '<td>' +
            '<div class="fw-semibold">' + product.name + '</div>' +
            '<small class="text-muted">' + (product.sku || "") + (product.sku ? " · " : "") + product.unit + '</small>' +
            '<input type="hidden" name="product_id[]" value="' + product.id + '">' +
        '</td>' +
        '<td>' +
            '<span class="badge ' + (stock <= 5 ? 'bg-warning text-dark' : 'bg-secondary') + '" id="stock-badge-' + product.id + '">' +
                stock +
            '</span>' +
        '</td>' +
        '<td>' +
            '<input type="number" name="quantity[]"' +
                   ' class="form-control form-control-sm qty-input"' +
                   ' min="1" value="1"' +
                   ' style="width:80px"' +
                   ' data-price="' + price + '"' +
                   ' data-stock="' + stock + '"' +
                   ' data-product-id="' + product.id + '">' +
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

 
    function updateRow() {
        const qtyInput  = tr.querySelector(".qty-input");
        const discInput = tr.querySelector(".discount-input");

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

        const lineTotal = warning ? 0 : Math.max(subtotal - discount, 0);
        tr.querySelector(".line-total-cell").textContent = fmt(lineTotal);
        tr.dataset.lineTotal = lineTotal;

        if (warning) {
            qtyInput.classList.add("is-invalid");
            warningRow.querySelector(".warning-text").textContent = warning;
            warningRow.classList.remove("d-none");
            tr.dataset.valid = "false";
        } else {
            qtyInput.classList.remove("is-invalid");
            warningRow.classList.add("d-none");
            tr.dataset.valid = "true";
        }

        recalcTotal();
    }

    tr.querySelector(".qty-input").addEventListener("input", updateRow);
    tr.querySelector(".discount-input").addEventListener("input", updateRow);

    tr.querySelector(".btn-remove").addEventListener("click", function () {
        tr.remove();
        warningRow.remove();
        updateVisibility();
        recalcTotal();
    });

    itemsBody.appendChild(tr);
    itemsBody.appendChild(warningRow);
    productModal.hide();
    updateVisibility();
    recalcTotal();
}
 
    /* ── modal: abrir ────────────────────────────────────────────────────── */
    btnAdd.addEventListener("click", function () {
        searchInput.value = "";
        document.querySelectorAll(".product-row").forEach(function (r) {
            r.style.display = "";
        });
        productModal.show();
        setTimeout(function () { searchInput.focus(); }, 300);
    });
 
    /* ── modal: busca em tempo real ──────────────────────────────────────── */
    searchInput.addEventListener("input", function () {
        var term = this.value.toLowerCase().trim();
        document.querySelectorAll(".product-row").forEach(function (row) {
            var name = row.dataset.name.toLowerCase();
            var sku  = row.dataset.sku.toLowerCase();
            row.style.display = (!term || name.includes(term) || sku.includes(term)) ? "" : "none";
        });
    });
 
    /* ── modal: botão "Selecionar" ───────────────────────────────────────── */
    document.querySelectorAll(".btn-pick").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var row = this.closest(".product-row");
            addProductRow({
                id    : row.dataset.id,
                name  : row.dataset.name,
                sku   : row.dataset.sku,
                unit  : row.dataset.unit,
                price : row.dataset.price,
                stock : row.dataset.stock,
            });
        });
    });
 
    /* ── validação antes de submeter ─────────────────────────────────────── */
    orderForm.addEventListener("submit", function (e) {
        const rows = itemsBody.querySelectorAll("tr[data-product-id]");

        if (rows.length === 0) {
            e.preventDefault();
            alert("Adicione pelo menos um produto ao pedido antes de salvar.");
            return;
        }

        let hasInvalid = false;
        rows.forEach(function (row) {
            if (row.dataset.valid === "false") hasInvalid = true;
        });

        if (hasInvalid) {
            e.preventDefault();
            alert("Corrija os itens destacados em vermelho antes de salvar.");
        }
    });
 
})();