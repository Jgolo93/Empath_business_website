(function () {
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ── Sticky header: sharpen shadow once the page has scrolled ──
    var header = document.querySelector('.site-header');
    if (header) {
        var updateHeader = function () {
            header.classList.toggle('is-scrolled', window.scrollY > 40);
        };
        updateHeader();
        window.addEventListener('scroll', updateHeader, { passive: true });
    }

    if (reduceMotion || typeof IntersectionObserver === 'undefined') return;

    // ── Scroll reveal ──
    // Groups whose children should fade in one-by-one (staggered via CSS nth-child delays).
    var STAGGER_SELECTORS = ['.articles-grid', '.topics-grid', '.faq-wrap', '.hero-stats'];
    // Standalone blocks that fade/slide in as a single unit.
    var SINGLE_SELECTORS = [
        '.featured-editorial', '.section-rule', '.newsletter-editorial',
        '.home-shop-wrap', '.brand-marquee-wrap'
    ];

    var revealObserver = new IntersectionObserver(function (entries, obs) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                obs.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });

    STAGGER_SELECTORS.forEach(function (sel) {
        document.querySelectorAll(sel).forEach(function (el) {
            el.classList.add('reveal-stagger');
            revealObserver.observe(el);
        });
    });
    SINGLE_SELECTORS.forEach(function (sel) {
        document.querySelectorAll(sel).forEach(function (el) {
            el.classList.add('reveal');
            revealObserver.observe(el);
        });
    });

    // ── Animated stat counters (e.g. "500+", "24/7", "R100", "< 1hr") ──
    // Counts up the first number found in the text, leaving any surrounding
    // characters (currency signs, slashes, "+", "hr", ...) untouched.
    var DURATION = 1100;
    var easeOutQuint = function (t) { return 1 - Math.pow(1 - t, 5); };

    var animateStat = function (el) {
        var original = el.textContent;
        var match = original.match(/\d+(\.\d+)?/);
        if (!match) return;
        var target = parseFloat(match[0]);
        var decimals = match[1] ? match[1].length - 1 : 0;
        var start = null;

        var step = function (timestamp) {
            if (start === null) start = timestamp;
            var progress = Math.min((timestamp - start) / DURATION, 1);
            var current = target * easeOutQuint(progress);
            var formatted = decimals ? current.toFixed(decimals) : Math.round(current).toString();
            el.textContent = original.slice(0, match.index) + formatted + original.slice(match.index + match[0].length);
            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = original;
            }
        };
        requestAnimationFrame(step);
    };

    var statObserver = new IntersectionObserver(function (entries, obs) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                animateStat(entry.target);
                obs.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    document.querySelectorAll('.hero-stat .num').forEach(function (el) {
        statObserver.observe(el);
    });

    // ── Cursor-spotlight hover on cards ──
    // Tracks pointer position within each card and exposes it as CSS custom
    // properties; animations.css turns that into a soft radial highlight.
    var SPOTLIGHT_SELECTORS = ['.article-card', '.topic-cell', '.featured-editorial'];
    SPOTLIGHT_SELECTORS.forEach(function (sel) {
        document.querySelectorAll(sel).forEach(function (card) {
            card.classList.add('spotlight-card');
            card.addEventListener('mousemove', function (e) {
                var rect = card.getBoundingClientRect();
                card.style.setProperty('--spot-x', (e.clientX - rect.left) + 'px');
                card.style.setProperty('--spot-y', (e.clientY - rect.top) + 'px');
            });
        });
    });
})();
