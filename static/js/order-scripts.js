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
        itemsBody.querySelectorAll("tr").forEach(function (row) {
            total += parseFloat(row.dataset.lineTotal || 0);
        });
        grandTotal.textContent = fmt(total);
    }
 
    function updateVisibility() {
        const hasRows = itemsBody.querySelectorAll("tr").length > 0;
        emptyRow.classList.toggle("d-none", hasRows);
        totalRow.classList.toggle("d-none", !hasRows);
    }
 
    /* ── adiciona linha de item na tabela ────────────────────────────────── */
    function addProductRow(product) {
        // Impede duplicata
        if (itemsBody.querySelector('tr[data-product-id="' + product.id + '"]')) {
            alert('"' + product.name + '" já foi adicionado. Ajuste a quantidade na linha existente.');
            productModal.hide();
            return;
        }
 
        const price     = parseFloat(product.price) || 0;
        const stock     = parseInt(product.stock)   || 0;
        const lineTotal = price * 1;  // quantidade inicial = 1
 
        const tr = document.createElement("tr");
        tr.dataset.productId = product.id;
        tr.dataset.lineTotal = lineTotal;
 
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
                       ' min="1" max="' + stock + '" value="1"' +
                       ' style="width:80px"' +
                       ' data-price="' + price + '"' +
                       ' data-stock="' + stock + '"' +
                       ' data-product-id="' + product.id + '">' +
            '</td>' +
            '<td class="text-end">' + fmt(price) + '</td>' +
            '<td class="text-end fw-semibold line-total-cell">' + fmt(lineTotal) + '</td>' +
            '<td class="text-center">' +
                '<button type="button" class="btn btn-sm btn-outline-danger btn-remove" title="Remover">' +
                    '<i class="fas fa-trash"></i>' +
                '</button>' +
            '</td>';
 
        /* evento: atualiza total ao alterar quantidade */
        tr.querySelector(".qty-input").addEventListener("input", function () {
            var qty      = parseInt(this.value) || 0;
            var maxStock = parseInt(this.dataset.stock);
            var priceVal = parseFloat(this.dataset.price);
 
            if (qty < 1) { qty = 1; this.value = 1; }
            if (qty > maxStock) {
                qty = maxStock;
                this.value = maxStock;
                this.classList.add("is-invalid");
            } else {
                this.classList.remove("is-invalid");
            }
 
            var lt = priceVal * qty;
            tr.dataset.lineTotal = lt;
            tr.querySelector(".line-total-cell").textContent = fmt(lt);
            recalcTotal();
        });
 
        /* evento: remover linha */
        tr.querySelector(".btn-remove").addEventListener("click", function () {
            tr.remove();
            updateVisibility();
            recalcTotal();
        });
 
        itemsBody.appendChild(tr);
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
        if (itemsBody.querySelectorAll("tr").length === 0) {
            e.preventDefault();
            alert("Adicione pelo menos um produto ao pedido antes de salvar.");
        }
    });
 
})();