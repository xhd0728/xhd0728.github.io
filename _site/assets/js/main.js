/* ==========================================================================
   Main JS — Vanilla ES6+ replacement for jQuery + plugins
   ========================================================================== */
(function () {
  'use strict';

  /* ------------------------------------------------------------------
     Greedy Navigation (Priority+ pattern)
     ------------------------------------------------------------------ */
  function initGreedyNav() {
    var nav = document.querySelector('.greedy-nav');
    if (!nav) return;

    var btn = nav.querySelector('.greedy-nav__toggle');
    var visibleList = nav.querySelector('.visible-links');
    var hiddenList = nav.querySelector('.hidden-links');
    var langMenu = nav.querySelector('.masthead__lang-menu');
    if (!btn || !visibleList || !hiddenList) return;
    var breaks = [];

    function width(el) {
      return Math.ceil(el.getBoundingClientRect().width);
    }

    function normalizePath(pathname) {
      return pathname.replace(/index\.html$/, '').replace(/\/+$/, '') || '/';
    }

    function initSamePageAnchorNav() {
      var currentPath = normalizePath(window.location.pathname);
      var links = nav.querySelectorAll('a[href*="#"]');

      links.forEach(function (link) {
        var href = link.getAttribute('href');
        if (!href) return;

        var url;
        try {
          url = new URL(href, window.location.href);
        } catch (e) {
          return;
        }

        if (!url.hash) return;
        if (url.origin !== window.location.origin) return;
        if (normalizePath(url.pathname) !== currentPath) return;

        var targetId = decodeURIComponent(url.hash.slice(1));
        var target = document.getElementById(targetId);
        if (!target) return;

        link.setAttribute('target', '_self');
        link.addEventListener('click', function (e) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          window.history.replaceState(null, '', '#' + targetId);
          hiddenList.classList.add('hidden');
          btn.classList.remove('close');
        });
      });
    }

    function updateNav() {
      var langToggle = langMenu ? langMenu.querySelector('.lang-menu__field') : null;
      var langMenuWidth = langMenu
        ? Math.max(width(langMenu), langToggle ? width(langToggle) : 0) + 18
        : 0;
      var availableSpace = btn.classList.contains('hidden')
        ? width(nav) - langMenuWidth
        : width(nav) - width(btn) - langMenuWidth - 30;

      if (width(visibleList) > availableSpace) {
        var lastVisibleItem = visibleList.lastElementChild;
        if (!lastVisibleItem) return;
        breaks.push(width(visibleList));
        hiddenList.prepend(lastVisibleItem);
        if (btn.classList.contains('hidden')) {
          btn.classList.remove('hidden');
        }
      } else {
        if (breaks.length > 0 && availableSpace > breaks[breaks.length - 1]) {
          var firstHiddenItem = hiddenList.firstElementChild;
          if (firstHiddenItem) {
            visibleList.append(firstHiddenItem);
            breaks.pop();
          }
        }
        if (breaks.length < 1) {
          btn.classList.add('hidden');
          hiddenList.classList.add('hidden');
        }
      }

      btn.setAttribute('count', breaks.length);

      if (width(visibleList) > availableSpace && visibleList.children.length > 0) {
        updateNav();
      }
    }

    btn.classList.add('hidden');
    window.addEventListener('resize', updateNav);

    btn.addEventListener('click', function () {
      hiddenList.classList.toggle('hidden');
      btn.classList.toggle('close');
    });

    hiddenList.addEventListener('click', function (e) {
      if (e.target && e.target.closest('a')) {
        hiddenList.classList.add('hidden');
        btn.classList.remove('close');
      }
    });

    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) {
        hiddenList.classList.add('hidden');
        btn.classList.remove('close');
      }
    });

    initSamePageAnchorNav();
    updateNav();
  }

  /* ------------------------------------------------------------------
     Author URLs dropdown (mobile)
     ------------------------------------------------------------------ */
  function initAuthorDropdown() {
    var btn = document.querySelector('.author__urls-wrapper button');
    if (!btn) return;

    btn.addEventListener('click', function () {
      var urls = document.querySelector('.author__urls');
      if (!urls) return;
      var isHidden = urls.style.display === 'none' || !urls.style.display;
      urls.style.display = isHidden ? 'block' : 'none';
      btn.classList.toggle('open');
    });
  }

  /* ------------------------------------------------------------------
     Sticky sidebar visibility (responsive)
     ------------------------------------------------------------------ */
  function initStickySidebar() {
    var urls = document.querySelector('.author__urls');
    var btn = document.querySelector('.author__urls-wrapper button');
    if (!urls) return;

    function update() {
      var isDesktop = !btn || window.getComputedStyle(btn).display === 'none';
      if (isDesktop) {
        urls.style.display = 'block';
      } else {
        urls.style.display = 'none';
      }
    }

    window.addEventListener('resize', update);
    update();
  }

  /* ------------------------------------------------------------------
     Lightbox using <dialog>
     ------------------------------------------------------------------ */
  function initLightbox() {
    var imageLinks = document.querySelectorAll(
      'a[href$=".jpg"], a[href$=".jpeg"], a[href$=".JPG"], a[href$=".png"], a[href$=".gif"], a[href$=".webp"]'
    );
    var paperImages = document.querySelectorAll('.paper-box-image img');
    if (!imageLinks.length && !paperImages.length) return;

    var dialog = document.createElement('dialog');
    dialog.className = 'lightbox-dialog';
    dialog.innerHTML =
      '<div class="lightbox-backdrop"></div>' +
      '<img class="lightbox-img" src="" alt="">' +
      '<button class="lightbox-close" aria-label="Close">&times;</button>';
    document.body.appendChild(dialog);

    var img = dialog.querySelector('.lightbox-img');
    var closeBtn = dialog.querySelector('.lightbox-close');
    var backdrop = dialog.querySelector('.lightbox-backdrop');
    var closingTimer = null;
    var isClosing = false;

    function openLightbox(src, alt) {
      if (closingTimer) {
        clearTimeout(closingTimer);
        closingTimer = null;
      }
      isClosing = false;
      dialog.classList.remove('is-closing');
      img.src = src;
      img.alt = alt || '';
      dialog.showModal();
    }

    function closeLightbox() {
      if (!dialog.open || isClosing) return;
      isClosing = true;
      dialog.classList.add('is-closing');
      closingTimer = window.setTimeout(function () {
        dialog.close();
        dialog.classList.remove('is-closing');
        isClosing = false;
        closingTimer = null;
      }, 220);
    }

    imageLinks.forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        openLightbox(link.href, link.title);
      });
    });

    paperImages.forEach(function (paperImg) {
      paperImg.style.cursor = 'zoom-in';
      paperImg.addEventListener('click', function (e) {
        e.stopPropagation();
        openLightbox(paperImg.src, paperImg.alt);
      });
    });

    closeBtn.addEventListener('click', closeLightbox);
    backdrop.addEventListener('click', closeLightbox);
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog) closeLightbox();
    });
    dialog.addEventListener('cancel', function (e) {
      e.preventDefault();
      closeLightbox();
    });
    dialog.addEventListener('close', function () {
      img.src = '';
      img.alt = '';
    });
  }

  function initPage() {
    initGreedyNav();
    initAuthorDropdown();
    initStickySidebar();
    initLightbox();
  }

  /* ------------------------------------------------------------------
     Init when DOM is ready
     ------------------------------------------------------------------ */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPage, { once: true });
  } else {
    initPage();
  }
})();
