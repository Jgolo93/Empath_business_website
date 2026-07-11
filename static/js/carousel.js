(function () {
    // Generic scroll-snap carousel: CSS handles the snapping and touch/trackpad
    // scrolling natively, this just wires the prev/next arrows to scroll by
    // one viewport's worth of track width.
    document.querySelectorAll('[data-carousel]').forEach(function (wrap) {
        var track = wrap.querySelector('[data-carousel-track]');
        var prevBtn = wrap.querySelector('[data-carousel-prev]');
        var nextBtn = wrap.querySelector('[data-carousel-next]');
        if (!track) return;

        function scrollByPage(direction) {
            track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: 'smooth' });
        }

        if (prevBtn) prevBtn.addEventListener('click', function () { scrollByPage(-1); });
        if (nextBtn) nextBtn.addEventListener('click', function () { scrollByPage(1); });
    });
})();
