(function () {
    // Turn "Label: Value" bullets inside the product description into two-column
    // spec rows. Shopify's descriptionHtml is freeform merchant content, so this
    // is a best-effort pattern match — anything that doesn't match a short
    // "Label:" prefix just renders as a normal bullet, unchanged.
    var descList = document.querySelectorAll('.pdp-description li');
    var specPattern = /^([A-Za-z][A-Za-z0-9 /'-]{1,28}):\s+(.+)$/;
    descList.forEach(function (li) {
        var match = li.textContent.match(specPattern);
        if (!match) return;
        li.classList.add('spec-row-item');
        li.textContent = '';
        var keySpan = document.createElement('span');
        keySpan.className = 'spec-k';
        keySpan.textContent = match[1];
        var valSpan = document.createElement('span');
        valSpan.className = 'spec-v';
        valSpan.textContent = match[2];
        li.appendChild(keySpan);
        li.appendChild(valSpan);
    });

    var variantSelect = document.getElementById('pdpVariantSelect');
    var priceEl = document.getElementById('pdpPrice');
    var addBtn = document.getElementById('pdpAddToCart');
    var checkoutBtn = document.getElementById('pdpCheckout');
    var statusEl = document.getElementById('pdpAddStatus');
    var quantityInput = document.getElementById('pdpQuantity');

    if (variantSelect && variantSelect.tagName === 'SELECT' && priceEl) {
        variantSelect.addEventListener('change', function () {
            var opt = variantSelect.options[variantSelect.selectedIndex];
            var price = parseFloat(opt.getAttribute('data-price'));
            var currency = opt.getAttribute('data-currency');
            if (!isNaN(price)) {
                priceEl.textContent = currency + ' ' + price.toFixed(2);
            }
        });
    }

    function addToCart() {
        var variantId = variantSelect ? variantSelect.value : null;
        if (!variantId) return Promise.reject(new Error('No variant selected'));
        var quantity = quantityInput ? Math.max(1, parseInt(quantityInput.value, 10) || 1) : 1;

        return fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variant_id: variantId, quantity: quantity })
        }).then(function (r) { return r.json(); });
    }

    function updateCartBadge(totalQuantity) {
        var cartFloat = document.getElementById('cartFloat');
        var cartFloatBadge = document.getElementById('cartFloatBadge');
        if (cartFloat && cartFloatBadge) {
            cartFloatBadge.textContent = totalQuantity;
            cartFloat.style.display = totalQuantity > 0 ? 'flex' : 'none';
        }
    }

    if (addBtn) {
        addBtn.addEventListener('click', function () {
            addBtn.disabled = true;
            statusEl.textContent = 'Adding...';

            addToCart()
                .then(function (data) {
                    addBtn.disabled = false;
                    if (data.success) {
                        statusEl.textContent = 'Added to cart (' + data.totalQuantity + ' item(s) total).';
                        statusEl.style.color = 'var(--accent2)';
                        updateCartBadge(data.totalQuantity);
                    } else {
                        statusEl.textContent = data.error || 'Could not add to cart.';
                        statusEl.style.color = '#dc2626';
                    }
                })
                .catch(function () {
                    addBtn.disabled = false;
                    statusEl.textContent = 'Network error — please try again.';
                    statusEl.style.color = '#dc2626';
                });
        });
    }

    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', function () {
            checkoutBtn.disabled = true;
            statusEl.textContent = 'Preparing checkout...';
            statusEl.style.color = '';

            addToCart()
                .then(function (data) {
                    if (data.success && data.checkoutUrl) {
                        updateCartBadge(data.totalQuantity);
                        window.location.href = data.checkoutUrl;
                    } else {
                        checkoutBtn.disabled = false;
                        statusEl.textContent = data.error || 'Could not start checkout.';
                        statusEl.style.color = '#dc2626';
                    }
                })
                .catch(function () {
                    checkoutBtn.disabled = false;
                    statusEl.textContent = 'Network error — please try again.';
                    statusEl.style.color = '#dc2626';
                });
        });
    }

    var notifyForm = document.getElementById('pdpNotifyForm');
    var notifyBtn = document.getElementById('pdpNotifyBtn');
    var notifyEmail = document.getElementById('pdpNotifyEmail');
    var notifyPhone = document.getElementById('pdpNotifyPhone');
    var notifyStatus = document.getElementById('pdpNotifyStatus');

    if (notifyForm && notifyBtn && notifyEmail && notifyStatus) {
        notifyBtn.addEventListener('click', function () {
            var email = notifyEmail.value.trim();
            var phone = notifyPhone ? notifyPhone.value.trim() : '';
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                notifyStatus.textContent = 'Please enter a valid email address.';
                notifyStatus.style.color = '#dc2626';
                return;
            }
            if (phone && !/^\+?[0-9]{9,15}$/.test(phone.replace(/[\s()-]/g, ''))) {
                notifyStatus.textContent = 'Please enter a valid phone number, or leave it blank.';
                notifyStatus.style.color = '#dc2626';
                return;
            }

            notifyBtn.disabled = true;
            notifyStatus.textContent = 'Saving...';
            notifyStatus.style.color = '';

            fetch('/api/notify-stock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    phone: phone,
                    variant_id: notifyForm.getAttribute('data-variant-id'),
                    product_handle: notifyForm.getAttribute('data-product-handle'),
                    product_title: notifyForm.getAttribute('data-product-title')
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    notifyBtn.disabled = false;
                    if (data.success) {
                        notifyStatus.textContent = phone
                            ? "You're on the list — we'll email and text you when it's back."
                            : "You're on the list — we'll email you when it's back.";
                        notifyStatus.style.color = 'var(--accent2)';
                        notifyEmail.disabled = true;
                        if (notifyPhone) notifyPhone.disabled = true;
                        notifyBtn.disabled = true;
                    } else {
                        notifyStatus.textContent = data.error || 'Could not save your details.';
                        notifyStatus.style.color = '#dc2626';
                    }
                })
                .catch(function () {
                    notifyBtn.disabled = false;
                    notifyStatus.textContent = 'Network error — please try again.';
                    notifyStatus.style.color = '#dc2626';
                });
        });
    }
})();
