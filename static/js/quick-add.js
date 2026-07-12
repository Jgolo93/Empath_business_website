(function () {
    // Delegated so it works on any page that renders a .product-card-quickadd button
    // (homepage, collection, search, recommendations) without needing a script tag
    // on each individual template.
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.product-card-quickadd');
        if (!btn) return;

        // The button sits inside a <a class="product-card"> — stop the card's own
        // navigation so quick-add doesn't also open the product page.
        e.preventDefault();
        e.stopPropagation();

        if (btn.disabled) return;
        var variantId = btn.getAttribute('data-variant-id');
        if (!variantId) return;

        var icon = btn.querySelector('.material-icons');
        var originalIcon = icon ? icon.textContent : '';
        btn.disabled = true;

        fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variant_id: variantId, quantity: 1 })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    var cartFloat = document.getElementById('cartFloat');
                    var cartFloatBadge = document.getElementById('cartFloatBadge');
                    if (cartFloat && cartFloatBadge) {
                        cartFloatBadge.textContent = data.totalQuantity;
                        cartFloat.style.display = data.totalQuantity > 0 ? 'flex' : 'none';
                    }
                    if (icon) icon.textContent = 'check';
                    btn.classList.add('is-added');
                    setTimeout(function () {
                        if (icon) icon.textContent = originalIcon;
                        btn.classList.remove('is-added');
                        btn.disabled = false;
                    }, 1200);
                } else {
                    if (icon) icon.textContent = 'error_outline';
                    setTimeout(function () {
                        if (icon) icon.textContent = originalIcon;
                        btn.disabled = false;
                    }, 1500);
                }
            })
            .catch(function () {
                if (icon) icon.textContent = 'error_outline';
                setTimeout(function () {
                    if (icon) icon.textContent = originalIcon;
                    btn.disabled = false;
                }, 1500);
            });
    });
})();
