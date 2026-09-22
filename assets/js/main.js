// Single, restrained reveal-on-scroll — not per-card, just per-section.
(function () {
  var els = document.querySelectorAll('[data-reveal]');
  if (!('IntersectionObserver' in window) || els.length === 0) {
    els.forEach(function (el) { el.classList.add('is-visible'); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
  els.forEach(function (el) { io.observe(el); });
})();

// Mobile nav toggle
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var menu = document.getElementById('mobile-menu');
  if (!toggle || !menu) return;

  function closeMenu() {
    menu.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open menu');
    document.body.style.overflow = '';
  }
  function openMenu() {
    menu.hidden = false;
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Close menu');
    document.body.style.overflow = 'hidden';
  }

  toggle.addEventListener('click', function () {
    if (menu.hidden) openMenu(); else closeMenu();
  });
  menu.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', closeMenu);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !menu.hidden) closeMenu();
  });
  // Close the mobile menu automatically if the viewport grows back to desktop width
  window.addEventListener('resize', function () {
    if (window.innerWidth > 900 && !menu.hidden) closeMenu();
  });
})();

// Contact form: submit via AJAX so we can redirect to our own branded
// thank-you page regardless of Formspree's plan tier (their server-side
// _next redirect is a paid-only feature; this client-side approach works
// on the free plan since AJAX submission itself is still free).
(function () {
  var form = document.getElementById('contact-form');
  if (!form) return;
  var errorBox = document.getElementById('contact-form-error');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (errorBox) errorBox.hidden = true;

    var submitBtn = form.querySelector('button[type="submit"]');
    var originalLabel = submitBtn ? submitBtn.textContent : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending…';
    }

    var redirectTo = form.querySelector('input[name="_next"]');
    var redirectUrl = redirectTo ? redirectTo.value : 'thank-you.html';

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'Accept': 'application/json' }
    }).then(function (response) {
      if (response.ok) {
        window.location.href = redirectUrl;
      } else {
        throw new Error('Form submission failed');
      }
    }).catch(function () {
      if (errorBox) errorBox.hidden = false;
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
      }
    });
  });
})();
