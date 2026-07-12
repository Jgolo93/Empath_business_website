(function () {
    // Generic scroll-snap carousel: CSS handles the snapping and touch/trackpad
    // scrolling natively, this just wires the prev/next arrows to scroll by
    // one viewport's worth of track width. Wraps with [data-carousel-autoplay="<ms>"]
    // also auto-advance (looping) at that interval, pausing on hover/touch/manual nav.
    document.querySelectorAll('[data-carousel]').forEach(function (wrap) {
        var track = wrap.querySelector('[data-carousel-track]');
        var prevBtn = wrap.querySelector('[data-carousel-prev]');
        var nextBtn = wrap.querySelector('[data-carousel-next]');
        if (!track) return;

        function scrollByPage(direction) {
            var atEnd = direction > 0 && track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
            var atStart = direction < 0 && track.scrollLeft <= 2;
            if (atEnd) {
                track.scrollTo({ left: 0, behavior: 'smooth' });
            } else if (atStart) {
                track.scrollTo({ left: track.scrollWidth, behavior: 'smooth' });
            } else {
                track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: 'smooth' });
            }
        }

        var intervalMs = parseInt(wrap.getAttribute('data-carousel-autoplay'), 10);
        var timer = null;
        function startAutoplay() {
            if (!intervalMs || timer) return;
            timer = setInterval(function () { scrollByPage(1); }, intervalMs);
        }
        function stopAutoplay() {
            if (timer) { clearInterval(timer); timer = null; }
        }

        if (prevBtn) prevBtn.addEventListener('click', function () { scrollByPage(-1); stopAutoplay(); });
        if (nextBtn) nextBtn.addEventListener('click', function () { scrollByPage(1); stopAutoplay(); });

        if (intervalMs) {
            startAutoplay();
            wrap.addEventListener('mouseenter', stopAutoplay);
            wrap.addEventListener('mouseleave', startAutoplay);
            wrap.addEventListener('touchstart', stopAutoplay, { passive: true });

            // Thumbnails live outside .carousel-wrap (as siblings under .pdp-gallery),
            // so clicking one wouldn't otherwise trigger the hover-based pause above.
            var gallery = wrap.closest('.pdp-gallery');
            if (gallery) {
                gallery.querySelectorAll('.pdp-thumbs img').forEach(function (thumb) {
                    thumb.addEventListener('click', stopAutoplay);
                });
            }
        }
    });
})();
