(function () {
    document.querySelectorAll('.cart-line-remove').forEach(function (btn) {
        btn.addEventListener('click', function () {
            btn.disabled = true;
            fetch('/api/cart/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ line_id: btn.getAttribute('data-line-id') })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        btn.disabled = false;
                        alert(data.error || 'Could not remove item.');
                    }
                })
                .catch(function () {
                    btn.disabled = false;
                    alert('Network error — please try again.');
                });
        });
    });

    var clearBtn = document.getElementById('cartClearBtn');
    var modal = document.getElementById('clearCartModal');
    var confirmBtn = document.getElementById('confirmClearCartBtn');

    function openModal() { modal.classList.add('active'); }
    function closeModal() { modal.classList.remove('active'); }

    if (clearBtn && modal && confirmBtn) {
        clearBtn.addEventListener('click', openModal);

        modal.querySelectorAll('[data-confirm-cancel]').forEach(function (el) {
            el.addEventListener('click', closeModal);
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('active')) closeModal();
        });

        confirmBtn.addEventListener('click', function () {
            confirmBtn.disabled = true;
            fetch('/api/cart/clear', { method: 'POST' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        confirmBtn.disabled = false;
                        closeModal();
                        alert(data.error || 'Could not clear cart.');
                    }
                })
                .catch(function () {
                    confirmBtn.disabled = false;
                    closeModal();
                    alert('Network error — please try again.');
                });
        });
    }
})();
